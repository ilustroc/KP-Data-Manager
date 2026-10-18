<?php

namespace App\Services\Imports;

use Closure;

final readonly class SearchPhonePreviewAnalyzer
{
    public function __construct(
        private SearchSpreadsheetPreviewReader $reader,
        private SearchPhoneOperatorMatcher $operators,
    ) {}

    /**
     * @param  array<string, string>  $mapping
     * @return array{headers: list<string>, rows: list<list<string|null>>, analysis: SearchImportPreviewAnalysis}
     */
    public function analyze(
        string $path,
        string $extension,
        array $mapping,
        int $previewLimit,
        int $errorLimit = 100,
    ): array {
        $errors = [];
        $scan = $this->scan(
            $path,
            $extension,
            $mapping,
            $previewLimit,
            function (array $error) use (&$errors, $errorLimit): void {
                if (count($errors) >= $errorLimit) {
                    return;
                }
                $errors[] = [
                    'row' => $error['row'],
                    'document' => $this->mask($error['document'], 2),
                    'phone' => $this->mask($error['phone'], 3),
                    'field' => $error['field'],
                    'error' => $error['error'],
                    'message' => $error['message'],
                ];
            },
        );

        return [
            'headers' => $scan['headers'],
            'rows' => $scan['rows'],
            'analysis' => $this->analysis($scan, $errors),
        ];
    }

    /**
     * @param  array<string, string>  $mapping
     * @param  Closure(array{row: int, document: string|null, phone: string|null, field: string, error: string, message: string, value: string}): void  $writeError
     */
    public function writeErrors(
        string $path,
        string $extension,
        array $mapping,
        Closure $writeError,
    ): SearchImportPreviewAnalysis {
        $scan = $this->scan($path, $extension, $mapping, 0, $writeError);

        return $this->analysis($scan, []);
    }

    /**
     * @param  array<string, string>  $mapping
     * @param  Closure(array{row: int, document: string|null, phone: string|null, field: string, error: string, message: string, value: string}): void  $writeError
     * @return array{headers: list<string>, rows: list<list<string|null>>, totalRows: int, emptyRows: int, invalidRows: array<int, true>, documents: array<string, true>, phones: array<string, true>, scopeDocuments: array<string, true>, duplicateDocumentPhones: int, invalidDocuments: int, invalidPhones: int, invalidOperators: int, ambiguousOperators: int, invalidDates: int, totalErrors: int, missingHeaders: int, extraHeaders: int}
     */
    private function scan(
        string $path,
        string $extension,
        array $mapping,
        int $previewLimit,
        Closure $writeError,
    ): array {
        $documents = [];
        $phones = [];
        $scopeDocuments = [];
        $pairs = [];
        $invalidRows = [];
        $totalErrors = 0;
        $duplicatePairs = 0;
        $invalidDocuments = 0;
        $invalidPhones = 0;
        $invalidOperators = 0;
        $ambiguousOperators = 0;
        $invalidDates = 0;
        $targetPositions = null;

        $appendError = function (
            int $row,
            ?string $document,
            ?string $phone,
            string $field,
            string $error,
            string $value,
        ) use (&$totalErrors, $writeError): void {
            $totalErrors++;
            $writeError([
                'row' => $row,
                'document' => $document,
                'phone' => $phone,
                'field' => $field,
                'error' => $error,
                'message' => $this->errorMessage($error),
                'value' => $value,
            ]);
        };

        $scan = $this->reader->read(
            $path,
            $extension,
            $previewLimit,
            function (int $row, array $headers, array $values) use (
                $mapping,
                &$documents,
                &$phones,
                &$scopeDocuments,
                &$pairs,
                &$invalidRows,
                &$duplicatePairs,
                &$invalidDocuments,
                &$invalidPhones,
                &$invalidOperators,
                &$ambiguousOperators,
                &$invalidDates,
                &$targetPositions,
                $appendError,
            ): void {
                if ($targetPositions === null) {
                    $positions = array_flip($headers);
                    $targetPositions = [];
                    foreach ($mapping as $target => $header) {
                        if (isset($positions[$header])) {
                            $targetPositions[$target] = $positions[$header];
                        }
                    }
                }
                $document = trim((string) ($values[$targetPositions['documento'] ?? -1] ?? null));
                $phone = trim((string) ($values[$targetPositions['telefono'] ?? -1] ?? null));
                $operatorRaw = (string) ($values[$targetPositions['operador_raw'] ?? -1] ?? '');
                $date = trim((string) ($values[$targetPositions['fecha_data'] ?? -1] ?? null));
                $rowHasError = false;
                $validDocument = preg_match('/\A[0-9]{8}\z/D', $document) === 1;
                $validPhone = $this->validPhone($phone);

                if (! $validDocument) {
                    $appendError($row, $document, $phone, 'documento', 'DOCUMENT_INVALID', $document);
                    $invalidDocuments++;
                    $rowHasError = true;
                } else {
                    $documents[$document] = true;
                }

                if (! $validPhone) {
                    $appendError($row, $document, $phone, 'telefono', 'PHONE_INVALID', $phone);
                    $invalidPhones++;
                    $rowHasError = true;
                } else {
                    $phones[$phone] = true;
                }

                $operator = $this->operators->match($operatorRaw);
                if ($operator['error'] !== null) {
                    $appendError(
                        $row,
                        $document,
                        $phone,
                        'operador_raw',
                        $operator['error'],
                        $operator['raw'],
                    );
                    if ($operator['error'] === 'OPERATOR_AMBIGUOUS') {
                        $ambiguousOperators++;
                    } else {
                        $invalidOperators++;
                    }
                    $rowHasError = true;
                }

                if (! $this->validDate($date)) {
                    $appendError($row, $document, $phone, 'fecha_data', 'DATE_INVALID', $date);
                    $invalidDates++;
                    $rowHasError = true;
                }

                if ($validPhone && $validDocument) {
                    $key = $document."\0".$phone;
                    if (isset($pairs[$key])) {
                        $appendError(
                            $row,
                            $document,
                            $phone,
                            'telefono',
                            'DUPLICATE_DOCUMENT_PHONE',
                            "DOCUMENTO={$document}; TELEFONO={$phone}",
                        );
                        $duplicatePairs++;
                        $rowHasError = true;
                    } else {
                        $pairs[$key] = true;
                    }
                }

                if ($rowHasError) {
                    $invalidRows[$row] = true;
                } else {
                    $scopeDocuments[$document] = true;
                }
            },
        );

        $expectedHeaders = ['DOCUMENTO', 'TELEFONO', 'OPERADOR', 'FECHA DATA'];
        $missingHeaders = count(array_diff($expectedHeaders, $scan['headers']));
        $extraHeaders = count(array_diff($scan['headers'], $expectedHeaders));
        if ($missingHeaders > 0) {
            $appendError(1, null, null, 'headers', 'HEADERS_MISSING', '');
        }
        if ($extraHeaders > 0) {
            $appendError(1, null, null, 'headers', 'HEADERS_EXTRA', '');
        }

        return [
            'headers' => $scan['headers'],
            'rows' => $scan['rows'],
            'totalRows' => $scan['total_rows'],
            'emptyRows' => $scan['empty_rows'],
            'invalidRows' => $invalidRows,
            'documents' => $documents,
            'phones' => $phones,
            'scopeDocuments' => $scopeDocuments,
            'duplicateDocumentPhones' => $duplicatePairs,
            'invalidDocuments' => $invalidDocuments,
            'invalidPhones' => $invalidPhones,
            'invalidOperators' => $invalidOperators,
            'ambiguousOperators' => $ambiguousOperators,
            'invalidDates' => $invalidDates,
            'totalErrors' => $totalErrors,
            'missingHeaders' => $missingHeaders,
            'extraHeaders' => $extraHeaders,
        ];
    }

    /**
     * @param  array{headers: list<string>, rows: list<list<string|null>>, totalRows: int, emptyRows: int, invalidRows: array<int, true>, documents: array<string, true>, phones: array<string, true>, scopeDocuments: array<string, true>, duplicateDocumentPhones: int, invalidDocuments: int, invalidPhones: int, invalidOperators: int, ambiguousOperators: int, invalidDates: int, totalErrors: int, missingHeaders: int, extraHeaders: int}  $scan
     * @param  list<array{row: int, document: string|null, phone: string|null, field: string, error: string, message: string}>  $errors
     */
    private function analysis(array $scan, array $errors): SearchImportPreviewAnalysis
    {
        return new SearchImportPreviewAnalysis(
            totalRows: $scan['totalRows'],
            validRows: $scan['totalRows'] - count($scan['invalidRows']),
            invalidRows: count($scan['invalidRows']),
            uniqueDocuments: count($scan['documents']),
            uniquePhones: count($scan['phones']),
            duplicateDocumentPhones: $scan['duplicateDocumentPhones'],
            invalidDocuments: $scan['invalidDocuments'],
            invalidPhones: $scan['invalidPhones'],
            invalidOperators: $scan['invalidOperators'],
            ambiguousOperators: $scan['ambiguousOperators'],
            invalidDates: $scan['invalidDates'],
            emptyRows: $scan['emptyRows'],
            missingHeaders: $scan['missingHeaders'],
            extraHeaders: $scan['extraHeaders'],
            estimatedScope: count($scan['scopeDocuments']),
            totalErrors: $scan['totalErrors'],
            errors: $errors,
        );
    }

    private function validPhone(string $phone): bool
    {
        return preg_match('/\A9[0-9]{8}\z/D', $phone) === 1
            && count(array_unique(str_split($phone))) > 1
            && ! in_array($phone, ['900000000', '911111111'], true);
    }

    private function validDate(string $value): bool
    {
        if (preg_match('/\A([0-9]{4})-([0-9]{2})-([0-9]{2})\z/D', $value, $parts) !== 1) {
            return false;
        }

        return checkdate((int) $parts[2], (int) $parts[3], (int) $parts[1]);
    }

    private function errorMessage(string $error): string
    {
        return match ($error) {
            'PHONE_INVALID' => 'El teléfono debe contener exactamente 9 dígitos, comenzar con 9 y superar las reglas de coherencia.',
            'OPERATOR_INVALID' => 'No se reconoció un operador permitido.',
            'OPERATOR_AMBIGUOUS' => 'Se detectó más de un operador permitido.',
            'DATE_INVALID' => 'FECHA DATA no contiene una fecha válida.',
            'DUPLICATE_DOCUMENT_PHONE' => 'La combinación DOCUMENTO + TELEFONO está repetida dentro del archivo.',
            'DOCUMENT_INVALID' => 'DNI debe contener exactamente 8 dígitos.',
            'HEADERS_MISSING' => 'Faltan encabezados requeridos.',
            'HEADERS_EXTRA' => 'El archivo contiene encabezados no permitidos.',
            default => 'El valor recibido no cumple el contrato.',
        };
    }

    private function mask(?string $value, int $visible): ?string
    {
        if ($value === null || $value === '') {
            return null;
        }
        $length = mb_strlen($value);
        if ($length <= $visible) {
            return str_repeat('*', $length);
        }

        return str_repeat('*', $length - $visible).mb_substr($value, -$visible);
    }
}
