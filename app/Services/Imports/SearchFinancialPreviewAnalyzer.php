<?php

namespace App\Services\Imports;

use App\DatasetCode;
use Closure;

final readonly class SearchFinancialPreviewAnalyzer
{
    public function __construct(
        private SearchSpreadsheetPreviewReader $reader,
        private SearchImportDefinitionRegistry $definitions,
        private SearchDmf5Contract $contract,
    ) {}

    /** @param array<string, string> $mapping @return array{headers:list<string>,rows:list<list<string|null>>,analysis:SearchImportPreviewAnalysis} */
    public function analyze(DatasetCode $dataset, string $path, string $extension, array $mapping, int $previewLimit, int $sampleLimit = 100): array
    {
        $errors = [];
        $warnings = [];
        $scan = $this->scan($dataset, $path, $extension, $mapping, $previewLimit, function (array $event) use (&$errors, &$warnings, $sampleLimit): void {
            $target = $event['warning'] ? $warnings : $errors;
            if (count($target) < $sampleLimit) {
                $target[] = $this->maskEvent($event);
            }
            if ($event['warning']) {
                $warnings = $target;
            } else {
                $errors = $target;
            }
        });

        return ['headers' => $scan['headers'], 'rows' => $scan['rows'], 'analysis' => $this->analysis($scan, $errors, $warnings)];
    }

    /** @param array<string,string> $mapping @param Closure(array{row:int,document:?string,phone:?string,field:string,error:string,message:string,value:string,warning:bool}):void $writeError */
    public function writeErrors(DatasetCode $dataset, string $path, string $extension, array $mapping, Closure $writeError): SearchImportPreviewAnalysis
    {
        return $this->analysis($this->scan($dataset, $path, $extension, $mapping, 0, $writeError), [], []);
    }

    /** @param array<string,string> $mapping */
    private function scan(DatasetCode $dataset, string $path, string $extension, array $mapping, int $previewLimit, Closure $event): array
    {
        $documents = [];
        $periods = [];
        $identities = [];
        $conflicts = [];
        $scope = [];
        $invalidRows = [];
        $publishableRows = 0;
        $totalErrors = 0;
        $warningsTotal = 0;
        $positions = null;
        $metrics = ['duplicates_exact' => 0, 'shifted_recovered' => 0];
        $append = function (int $row, ?string $document, string $field, string $code, string $value, bool $warning = false) use (&$totalErrors, &$warningsTotal, $event): void {
            $warning ? $warningsTotal++ : $totalErrors++;
            $event(['row' => $row, 'document' => $document, 'phone' => null, 'field' => $field, 'error' => $code, 'message' => $this->message($code), 'value' => $value, 'warning' => $warning]);
        };
        $readerScan = $this->reader->read($path, $extension, $previewLimit, function (int $row, array $headers, array $values) use ($dataset, $mapping, &$positions, &$documents, &$periods, &$identities, &$conflicts, &$scope, &$invalidRows, &$publishableRows, &$metrics, $append): void {
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
                $scope[$document] = true;
            }
            $normalized = $this->normalize($dataset, $input);
            foreach ($normalized['errors'] as [$field, $code, $value]) {
                $append($row, $document, $field, $code, $value);
                $rowErrors = true;
            }
            foreach ($normalized['warnings'] as [$field, $code, $value]) {
                $append($row, $document, $field, $code, $value, true);
                if ($code === 'SBS_DETAIL_SHIFTED_COLUMNS_RECOVERED') {
                    $metrics['shifted_recovered']++;
                }
            }
            if ($rowErrors) {
                $invalidRows[$row] = true;

                return;
            }
            $valuesNormalized = $normalized['values'];
            $period = $valuesNormalized['periodo'] ?? $valuesNormalized['fecha_reporte_sbs'] ?? null;
            if ($period !== null) {
                $periods[$period] = true;
            }
            $identity = json_encode([$dataset->value, $document, $valuesNormalized], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
            if (isset($identities[$identity])) {
                $metrics['duplicates_exact']++;
                $append($row, $document, 'registro', 'DUPLICATE_EXACT', '', true);

                return;
            }
            $identities[$identity] = true;
            if ($dataset === DatasetCode::SbsResumen) {
                $key = $document."\0".$valuesNormalized['fecha_reporte_sbs']."\0".$valuesNormalized['cod_sbs'];
                $signature = json_encode($valuesNormalized, JSON_THROW_ON_ERROR);
                if (isset($conflicts[$key]) && $conflicts[$key] !== $signature) {
                    $append($row, $document, 'cod_sbs', 'SBS_SUMMARY_CONFLICT', $valuesNormalized['cod_sbs']);
                    $invalidRows[$row] = true;

                    return;
                }
                $conflicts[$key] = $signature;
            }
            $publishableRows++;
        });
        $expected = $this->definitions->resolve($dataset)->expectedHeaders();
        $missing = count(array_diff($expected, $readerScan['headers']));
        $extra = count(array_diff($readerScan['headers'], $expected));
        if ($missing > 0) {
            $append(1, null, 'headers', 'HEADERS_MISSING', '');
        }
        if ($extra > 0) {
            $append(1, null, 'headers', 'HEADERS_EXTRA', '');
        }

        return ['headers' => $readerScan['headers'], 'rows' => $readerScan['rows'], 'totalRows' => $readerScan['total_rows'], 'emptyRows' => $readerScan['empty_rows'], 'documents' => $documents, 'periods' => $periods, 'identities' => $identities, 'scope' => $scope, 'invalidRows' => $invalidRows, 'publishableRows' => $publishableRows, 'totalErrors' => $totalErrors, 'warningsTotal' => $warningsTotal, 'missing' => $missing, 'extra' => $extra, 'metrics' => $metrics];
    }

    /** @return array{values:array<string,mixed>,errors:list<array{string,string,string}>,warnings:list<array{string,string,string}>} */
    private function normalize(DatasetCode $dataset, Closure $input): array
    {
        $text = static fn (string $field): ?string => ($value = preg_replace('/\s+/u', ' ', $input($field))) === '' ? null : $value;
        $digits = static fn (?string $value, int $length): bool => $value !== null && preg_match('/\A[0-9]{'.$length.'}\z/D', $value) === 1;
        $period = function (?string $value): bool {
            if ($value === null || preg_match('/\A'.substr($this->contract->periodPattern(), 1, -1).'\z/D', $value) !== 1) {
                return false;
            }

            $year = (int) mb_substr($value, 0, 4);
            $month = (int) mb_substr($value, 4, 2);

            return $year >= 1900 && $year <= 2100 && $month >= 1 && $month <= 12;
        };
        $decimal = static function (?string $value, int $scale = 2): ?string {
            if ($value === null || preg_match('/\A([0-9]+)(?:\.([0-9]{1,'.$scale.'}))?\z/D', $value, $match) !== 1) {
                return null;
            }

            $integer = ltrim($match[1], '0') ?: '0';

            return $integer.'.'.str_pad($match[2] ?? '', $scale, '0');
        };
        $scaled = static function (string $value, int $scale): int {
            [$integer, $fraction] = array_pad(explode('.', $value, 2), 2, '');

            return ((int) $integer * (10 ** $scale)) + (int) str_pad($fraction, $scale, '0');
        };
        $values = [];
        $errors = [];
        $warnings = [];
        if ($dataset === DatasetCode::SbsResumen) {
            $values = ['cod_sbs' => $text('cod_sbs'), 'fecha_reporte_sbs' => $text('fecha_reporte_sbs'), 'cantidad_empresas' => $text('cantidad_empresas')];
            foreach (['normal', 'cpp', 'deficiente', 'dudoso', 'perdida'] as $field) {
                $values['calificacion_'.$field] = $decimal($text('calificacion_'.$field), 4);
                if ($text('calificacion_'.$field) !== null && ($values['calificacion_'.$field] === null || (float) $values['calificacion_'.$field] > 100)) {
                    $errors[] = ['calificacion_'.$field, 'PERCENTAGE_INVALID', (string) $text('calificacion_'.$field)];
                }
            }
            if (! $digits($values['cod_sbs'], 10)) {
                $errors[] = ['cod_sbs', 'COD_SBS_INVALID', (string) $values['cod_sbs']];
            }
            if (! $period($values['fecha_reporte_sbs'])) {
                $errors[] = ['fecha_reporte_sbs', 'PERIOD_INVALID', (string) $values['fecha_reporte_sbs']];
            }
            if ($values['cantidad_empresas'] === null || preg_match('/\A[0-9]+\z/D', $values['cantidad_empresas']) !== 1) {
                $errors[] = ['cantidad_empresas', 'COMPANY_COUNT_INVALID', (string) $values['cantidad_empresas']];
            } else {
                $values['cantidad_empresas'] = (int) $values['cantidad_empresas'];
            }
            $percentages = array_slice($values, 3);
            if (! $errors && ! in_array(null, $percentages, true)) {
                $sum = array_sum(array_map(static fn (string $value): int => $scaled($value, 4), $percentages));
                if ($sum < 995000 || $sum > 1005000) {
                    $errors[] = ['calificaciones', 'SBS_PERCENTAGE_TOTAL_INVALID', number_format($sum / 10000, 4, '.', '')];
                }
            }
        } elseif ($dataset === DatasetCode::SbsDetalle) {
            foreach (['fecha_reporte_sbs', 'cod_sbs', 'entidad', 'tipo_credito', 'condicion', 'monto', 'dias_atraso'] as $field) {
                $values[$field] = $text($field);
            }
            if (! $period($values['fecha_reporte_sbs'])) {
                $errors[] = ['fecha_reporte_sbs', 'PERIOD_INVALID', (string) $values['fecha_reporte_sbs']];
            }
            if (! $digits($values['cod_sbs'], 10)) {
                $errors[] = ['cod_sbs', 'COD_SBS_INVALID', (string) $values['cod_sbs']];
            }
            $condition = $values['condicion'] === null ? null : mb_strtoupper($values['condicion']);
            $type = $values['tipo_credito'] === null ? null : mb_strtoupper($values['tipo_credito']);
            $shift = $this->contract->shiftedDetailFields();
            if (in_array($type, $this->contract->sbsConditions(), true) && $decimal($condition) !== null && (! $shift['requires_days_atraso_empty'] || $values['dias_atraso'] === null) && ($values['monto'] === null || preg_match('/\A[0-9]+\z/D', $values['monto']) === 1)) {
                $values['tipo_credito'] = null;
                $values['condicion'] = $type;
                $values['dias_atraso'] = $values['monto'] === null ? null : (int) $values['monto'];
                $values['monto'] = $condition;
                $warnings[] = ['tipo_credito', 'SBS_DETAIL_SHIFTED_COLUMNS_RECOVERED', ''];
            } elseif (in_array($type, $this->contract->sbsConditions(), true) && $values['tipo_credito'] !== null) {
                $errors[] = ['tipo_credito', 'SBS_DETAIL_COLUMN_SHIFT_AMBIGUOUS', $values['tipo_credito']];
            }
            $values['condicion'] = $values['condicion'] === null ? null : mb_strtoupper($values['condicion']);
            if ($values['condicion'] !== null && ! in_array($values['condicion'], $this->contract->sbsConditions(), true)) {
                $errors[] = ['condicion', 'CONDITION_INVALID', $values['condicion']];
            }
            $amount = $decimal($values['monto']);
            if ($values['monto'] !== null && $amount === null) {
                $errors[] = ['monto', 'AMOUNT_INVALID', $values['monto']];
            } $values['monto'] = $amount;
            if ($values['dias_atraso'] !== null && preg_match('/\A[0-9]+\z/D', $values['dias_atraso']) !== 1) {
                $errors[] = ['dias_atraso', 'DAYS_OVERDUE_INVALID', $values['dias_atraso']];
            } elseif ($values['dias_atraso'] !== null) {
                $values['dias_atraso'] = (int) $values['dias_atraso'];
            }
        } else {
            $values = ['periodo' => $text('periodo'), 'ruc' => $text('ruc'), 'nombre_empresa' => $text('nombre_empresa'), 'sueldo' => $text('sueldo'), 'situacion' => $text('situacion')];
            if (! $period($values['periodo'])) {
                $errors[] = ['periodo', 'PERIOD_INVALID', (string) $values['periodo']];
            } if (! $digits($values['ruc'], 11)) {
                $errors[] = ['ruc', 'RUC_INVALID', (string) $values['ruc']];
            }
            $salary = $decimal($values['sueldo']);
            if ($values['sueldo'] !== null && $salary === null) {
                $errors[] = ['sueldo', 'SALARY_INVALID', $values['sueldo']];
            } $values['sueldo'] = $salary;
            $values['situacion'] = $values['situacion'] === null ? null : mb_strtoupper($values['situacion']);
        }

        return compact('values', 'errors', 'warnings');
    }

    private function analysis(array $scan, array $errors, array $warnings): SearchImportPreviewAnalysis
    {
        return new SearchImportPreviewAnalysis(totalRows: $scan['totalRows'], validRows: $scan['publishableRows'], invalidRows: count($scan['invalidRows']), uniqueDocuments: count($scan['documents']), uniquePhones: 0, duplicateDocumentPhones: 0, invalidDocuments: 0, invalidPhones: 0, invalidOperators: 0, ambiguousOperators: 0, invalidDates: 0, emptyRows: $scan['emptyRows'], missingHeaders: $scan['missing'], extraHeaders: $scan['extra'], estimatedScope: count($scan['scope']), totalErrors: $scan['totalErrors'], errors: $errors, warningsTotal: $scan['warningsTotal'], warnings: $warnings, metrics: $scan['metrics'] + ['periods' => count($scan['periods']), 'unique_records' => count($scan['identities'])]);
    }

    private function maskEvent(array $event): array
    {
        $event['document'] = $this->mask($event['document']);
        unset($event['value'], $event['warning']);

        return $event;
    }

    private function mask(?string $value): ?string
    {
        return $value === null || $value === '' ? null : (mb_strlen($value) <= 2 ? str_repeat('*', mb_strlen($value)) : str_repeat('*', mb_strlen($value) - 2).mb_substr($value, -2));
    }

    private function message(string $code): string
    {
        return match ($code) {
            'DOCUMENT_INVALID' => 'DNI debe contener exactamente 8 dígitos.', 'PERIOD_INVALID' => 'El periodo debe tener formato YYYYMM válido.', 'COD_SBS_INVALID' => 'El código SBS debe contener exactamente 10 dígitos.', 'PERCENTAGE_INVALID' => 'La calificación debe ser un decimal entre 0 y 100.', 'SBS_PERCENTAGE_TOTAL_INVALID' => 'La suma de calificaciones está fuera de la tolerancia permitida.', 'SBS_SUMMARY_CONFLICT' => 'El mismo resumen SBS contiene valores diferentes.', 'SBS_DETAIL_SHIFTED_COLUMNS_RECOVERED' => 'Se recuperó una fila con columnas desplazadas.', 'SBS_DETAIL_COLUMN_SHIFT_AMBIGUOUS' => 'La fila parece desplazada, pero no puede recuperarse de forma segura.', 'CONDITION_INVALID' => 'La condición SBS no pertenece al catálogo permitido.', 'AMOUNT_INVALID' => 'El monto debe ser un decimal no negativo.', 'DAYS_OVERDUE_INVALID' => 'Los días de atraso deben ser un entero no negativo.', 'RUC_INVALID' => 'El RUC debe contener exactamente 11 dígitos.', 'SALARY_INVALID' => 'El sueldo debe ser un decimal no negativo.', 'DUPLICATE_EXACT' => 'El registro canónico está repetido en el archivo.', 'HEADERS_MISSING' => 'Faltan encabezados requeridos.', 'HEADERS_EXTRA' => 'El archivo contiene encabezados no permitidos.', default => 'El valor recibido no cumple el contrato.',
        };
    }
}
