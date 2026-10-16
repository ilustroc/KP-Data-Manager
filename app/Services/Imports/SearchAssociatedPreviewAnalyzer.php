<?php

namespace App\Services\Imports;

use App\DatasetCode;
use Closure;

final readonly class SearchAssociatedPreviewAnalyzer
{
    public function __construct(
        private SearchSpreadsheetPreviewReader $reader,
        private SearchImportDefinitionRegistry $definitions,
    ) {}

    /**
     * @param  array<string, string>  $mapping
     * @return array{headers: list<string>, rows: list<list<string|null>>, analysis: SearchImportPreviewAnalysis}
     */
    public function analyze(DatasetCode $dataset, string $path, string $extension, array $mapping, int $previewLimit, int $sampleLimit = 100): array
    {
        $errors = [];
        $warnings = [];
        $scan = $this->scan($dataset, $path, $extension, $mapping, $previewLimit, function (array $event) use (&$errors, &$warnings, $sampleLimit): void {
            if ($event['warning']) {
                if (count($warnings) < $sampleLimit) {
                    $warnings[] = $this->maskEvent($event);
                }

                return;
            }
            if (count($errors) < $sampleLimit) {
                $errors[] = $this->maskEvent($event);
            }
        });

        return ['headers' => $scan['headers'], 'rows' => $scan['rows'], 'analysis' => $this->analysis($scan, $errors, $warnings)];
    }

    /** @param array<string, string> $mapping @param Closure(array{row:int,document:?string,phone:?string,field:string,error:string,message:string,value:string,warning:bool}): void $writeError */
    public function writeErrors(DatasetCode $dataset, string $path, string $extension, array $mapping, Closure $writeError): SearchImportPreviewAnalysis
    {
        return $this->analysis($this->scan($dataset, $path, $extension, $mapping, 0, $writeError), [], []);
    }

    /** @param array<string, string> $mapping @param Closure(array{row:int,document:?string,phone:?string,field:string,error:string,message:string,value:string,warning:bool}): void $event */
    private function scan(DatasetCode $dataset, string $path, string $extension, array $mapping, int $previewLimit, Closure $event): array
    {
        $documents = [];
        $identities = [];
        $scope = [];
        $conflicts = [];
        $invalidRows = [];
        $publishableRows = 0;
        $metrics = ['duplicates_exact' => 0, 'empty_address_rows' => 0, 'plate_conflicts' => 0, 'property_conflicts' => 0, 'with_plate' => 0, 'without_plate' => 0];
        $totalErrors = 0;
        $warningsTotal = 0;
        $positions = null;
        $definition = $this->definition($dataset);
        $append = function (int $row, ?string $document, string $field, string $code, string $value, bool $warning = false) use (&$totalErrors, &$warningsTotal, $event): void {
            $warning ? $warningsTotal++ : $totalErrors++;
            $event(['row' => $row, 'document' => $document, 'phone' => null, 'field' => $field, 'error' => $code, 'message' => $this->message($code), 'value' => $value, 'warning' => $warning]);
        };
        $scan = $this->reader->read($path, $extension, $previewLimit, function (int $row, array $headers, array $values) use ($dataset, $mapping, &$positions, &$documents, &$identities, &$scope, &$conflicts, &$invalidRows, &$publishableRows, &$metrics, $append): void {
            if ($positions === null) {
                $positions = array_flip($headers);
                foreach ($mapping as $target => $header) {
                    $positions[$target] = $positions[$header] ?? -1;
                }
            }
            $input = static fn (string $field): string => trim((string) ($values[$positions[$field] ?? -1] ?? ''));
            $document = $input('documento');
            $rowErrors = false;
            if (preg_match('/\A[0-9]{8}\z/D', $document) !== 1) {
                $append($row, $document, 'documento', 'DOCUMENT_INVALID', $document);
                $rowErrors = true;
            } else {
                $documents[$document] = true;
            }
            $normalized = $this->normalize($dataset, $input);
            foreach ($normalized['errors'] as [$field, $code, $value]) {
                $append($row, $document, $field, $code, $value);
                $rowErrors = true;
            }
            if ($rowErrors) {
                $invalidRows[$row] = true;

                return;
            }
            if ($dataset === DatasetCode::Direcciones && $normalized['skip']) {
                $metrics['empty_address_rows']++;
                $append($row, $document, 'direccion', 'EMPTY_ADDRESS', '', true);
                $scope[$document] = true;

                return;
            }
            if ($dataset === DatasetCode::Vehiculos) {
                $normalized['values']['placa'] === null ? $metrics['without_plate']++ : $metrics['with_plate']++;
            }
            $identity = $this->identity($dataset, $document, $normalized['values']);
            if (isset($identities[$identity])) {
                $metrics['duplicates_exact']++;
                $append($row, $document, 'registro', 'DUPLICATE_EXACT', $identity, true);

                return;
            }
            $identities[$identity] = true;
            $conflict = $this->conflict($dataset, $document, $normalized['values']);
            if ($conflict !== null) {
                [$key, $signature, $field, $code] = $conflict;
                if (isset($conflicts[$key]) && $conflicts[$key] !== $signature) {
                    $metrics[$code === 'VEHICLE_PLATE_CONFLICT' ? 'plate_conflicts' : 'property_conflicts']++;
                    $append($row, $document, $field, $code, $key);
                    $invalidRows[$row] = true;

                    return;
                }
                $conflicts[$key] = $signature;
            }
            $scope[$document] = true;
            $publishableRows++;
        });
        $missing = count(array_diff($this->definition($dataset)->expectedHeaders(), $scan['headers']));
        $extra = count(array_diff($scan['headers'], $this->definition($dataset)->expectedHeaders()));
        if ($missing > 0) {
            $append(1, null, 'headers', 'HEADERS_MISSING', '');
        }
        if ($extra > 0) {
            $append(1, null, 'headers', 'HEADERS_EXTRA', '');
        }
        $metrics += $this->datasetMetrics($dataset, $identities, $scope);

        return compact('scan', 'documents', 'invalidRows', 'publishableRows', 'metrics', 'totalErrors', 'warningsTotal', 'missing', 'extra') + ['headers' => $scan['headers'], 'rows' => $scan['rows'], 'totalRows' => $scan['total_rows'], 'emptyRows' => $scan['empty_rows'], 'scope' => $scope];
    }

    /** @return array{values:array<string,string|int|null>,errors:list<array{string,string,string}>,skip:bool} */
    private function normalize(DatasetCode $dataset, Closure $input): array
    {
        $text = static fn (string $field): ?string => ($value = preg_replace('/\s+/u', ' ', $input($field))) === '' ? null : $value;
        $values = [];
        $errors = [];
        if ($dataset === DatasetCode::Correos) {
            $original = $text('correo_original');
            $email = $original === null ? null : mb_strtolower($original);
            if ($email === null || mb_strlen($email) > 254 || substr_count($email, '@') !== 1 || str_contains($email, ' ') || ! str_contains((string) strrchr($email, '@'), '.') || $email === 'sincorreo@sincorreo.com') {
                $errors[] = ['correo_original', 'EMAIL_INVALID', (string) $original];
            }

            return ['values' => ['correo' => $email, 'correo_original' => $original], 'errors' => $errors, 'skip' => false];
        }
        if ($dataset === DatasetCode::Direcciones) {
            foreach (['direccion', 'departamento', 'provincia', 'distrito', 'data_procedencia'] as $field) {
                $values[$field] = $text($field);
            }
            $values['procedencia_anio'] = preg_match('/(?<![0-9])([0-9]{4})(?![0-9])/', (string) $values['data_procedencia'], $match) === 1 ? (int) $match[1] : null;

            return ['values' => $values, 'errors' => [], 'skip' => $values['direccion'] === null && $values['departamento'] === null && $values['provincia'] === null && $values['distrito'] === null];
        }
        if ($dataset === DatasetCode::Vehiculos) {
            foreach (['nombre_completo_fuente', 'clase', 'marca', 'placa_original'] as $field) {
                $values[$field] = $text($field);
            }
            $values['placa'] = $values['placa_original'] === null ? null : mb_strtoupper($values['placa_original']);
            foreach (['anio_compra', 'anio_fabricacion'] as $field) {
                $values[$field] = $this->year($input($field), $field, $errors);
            }
            $transfer = $input('numero_transferencias');
            $values['numero_transferencias'] = $transfer === '' ? null : (preg_match('/\A[0-9]+\z/D', $transfer) === 1 ? (int) $transfer : null);
            if ($transfer !== '' && $values['numero_transferencias'] === null) {
                $errors[] = ['numero_transferencias', 'TRANSFER_INVALID', $transfer];
            }

            return ['values' => $values, 'errors' => $errors, 'skip' => false];
        }
        foreach (['partida_registral', 'zona_registral', 'oficina'] as $field) {
            $values[$field] = $text($field);
        }
        if ($values['partida_registral'] === null) {
            $errors[] = ['partida_registral', 'PROPERTY_INVALID', ''];
        } else {
            $values['partida_registral'] = mb_strtoupper($values['partida_registral']);
        }

        return ['values' => $values, 'errors' => $errors, 'skip' => false];
    }

    /** @param list<array{string,string,string}> $errors */
    private function year(string $value, string $field, array &$errors): ?int
    {
        if ($value === '') {
            return null;
        }
        if (preg_match('/\A(?:19|20)[0-9]{2}\z/D', $value) !== 1) {
            $errors[] = [$field, 'YEAR_INVALID', $value];

            return null;
        }

        return (int) $value;
    }

    /** @param array<string,string|int|null> $values */
    private function identity(DatasetCode $dataset, string $document, array $values): string
    {
        if ($dataset === DatasetCode::Correos) {
            $values = ['correo' => $values['correo']];
        }

        return json_encode([$dataset->value, $document, $values], JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION | JSON_THROW_ON_ERROR);
    }

    /** @param array<string,string|int|null> $values @return array{string,string,string,string}|null */
    private function conflict(DatasetCode $dataset, string $document, array $values): ?array
    {
        if ($dataset === DatasetCode::Vehiculos && $values['placa'] !== null) {
            return [$document."\0".$values['placa'], json_encode([$values['nombre_completo_fuente'], $values['clase'], $values['anio_compra'], $values['anio_fabricacion'], $values['marca'], $values['numero_transferencias']], JSON_THROW_ON_ERROR), 'placa', 'VEHICLE_PLATE_CONFLICT'];
        }
        if ($dataset === DatasetCode::Propiedades) {
            return [$document."\0".$values['partida_registral'], json_encode([$values['zona_registral'], $values['oficina']], JSON_THROW_ON_ERROR), 'partida_registral', 'PROPERTY_CONFLICT'];
        }

        return null;
    }

    private function definition(DatasetCode $dataset): SearchImportDefinition
    {
        return $this->definitions->resolve($dataset);
    }

    /** @param array<string,true> $identities @param array<string,true> $scope @return array<string,int> */
    private function datasetMetrics(DatasetCode $dataset, array $identities, array $scope): array
    {
        return match ($dataset) {
            DatasetCode::Correos => ['unique_emails' => count($identities)], DatasetCode::Direcciones => ['addresses' => count($identities)], DatasetCode::Vehiculos => ['vehicles' => count($identities)], DatasetCode::Propiedades => ['properties' => count($identities)], default => []
        };
    }

    /** @param array<string,mixed> $scan @param list<array<string,mixed>> $errors @param list<array<string,mixed>> $warnings */
    private function analysis(array $scan, array $errors, array $warnings): SearchImportPreviewAnalysis
    {
        return new SearchImportPreviewAnalysis(totalRows: $scan['totalRows'], validRows: $scan['publishableRows'], invalidRows: count($scan['invalidRows']), uniqueDocuments: count($scan['documents']), uniquePhones: 0, duplicateDocumentPhones: 0, invalidDocuments: 0, invalidPhones: 0, invalidOperators: 0, ambiguousOperators: 0, invalidDates: 0, emptyRows: $scan['emptyRows'], missingHeaders: $scan['missing'], extraHeaders: $scan['extra'], estimatedScope: count($scan['scope']), totalErrors: $scan['totalErrors'], errors: $errors, warningsTotal: $scan['warningsTotal'], warnings: $warnings, metrics: $scan['metrics']);
    }

    /** @param array<string,mixed> $event @return array{row:int,document:?string,phone:?string,field:string,error:string,message:string} */
    private function maskEvent(array $event): array
    {
        $event['document'] = $this->mask($event['document'], 2);
        unset($event['value'], $event['warning']);

        return $event;
    }

    private function mask(?string $value, int $visible): ?string
    {
        if ($value === null || $value === '') {
            return null;
        }

        return mb_strlen($value) <= $visible ? str_repeat('*', mb_strlen($value)) : str_repeat('*', mb_strlen($value) - $visible).mb_substr($value, -$visible);
    }

    private function message(string $code): string
    {
        return match ($code) {
            'DOCUMENT_INVALID' => 'DNI debe contener exactamente 8 dígitos.', 'EMAIL_INVALID' => 'El correo no cumple el formato permitido.', 'EMPTY_ADDRESS' => 'La fila no contiene ningún dato de dirección.', 'YEAR_INVALID' => 'El año debe ser un entero entre 1900 y 2100.', 'TRANSFER_INVALID' => 'El número de transferencias debe ser un entero mayor o igual a cero.', 'PROPERTY_INVALID' => 'La partida registral es obligatoria.', 'DUPLICATE_EXACT' => 'El registro canónico está repetido en el archivo.', 'VEHICLE_PLATE_CONFLICT' => 'La misma placa tiene información diferente para el mismo documento.', 'PROPERTY_CONFLICT' => 'La misma partida tiene zona u oficina diferente para el mismo documento.', 'HEADERS_MISSING' => 'Faltan encabezados requeridos.', 'HEADERS_EXTRA' => 'El archivo contiene encabezados no permitidos.', default => 'El valor recibido no cumple el contrato.',
        };
    }
}
