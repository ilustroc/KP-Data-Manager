<?php

namespace App\Services\Imports;

final readonly class SearchImportPreviewAnalysis
{
    /**
     * @param  list<array{row: int, document: string|null, phone: string|null, field: string, error: string, message: string}>  $errors
     * @param  list<array{row: int, document: string|null, phone: string|null, field: string, error: string, message: string}>  $warnings
     * @param  array<string, int>  $metrics
     */
    public function __construct(
        public int $totalRows,
        public int $validRows,
        public int $invalidRows,
        public int $uniqueDocuments,
        public int $uniquePhones,
        public int $duplicateDocumentPhones,
        public int $invalidDocuments,
        public int $invalidPhones,
        public int $invalidOperators,
        public int $ambiguousOperators,
        public int $invalidDates,
        public int $emptyRows,
        public int $missingHeaders,
        public int $extraHeaders,
        public int $estimatedScope,
        public int $totalErrors,
        public array $errors,
        public int $warningsTotal = 0,
        public array $warnings = [],
        public array $metrics = [],
    ) {}

    public function isReady(): bool
    {
        return $this->invalidRows === 0
            && $this->missingHeaders === 0
            && $this->extraHeaders === 0
            && $this->totalRows > 0;
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return get_object_vars($this);
    }

    /** @param array<string, mixed> $values */
    public static function fromArray(array $values): self
    {
        return new self(
            totalRows: (int) $values['totalRows'],
            validRows: (int) $values['validRows'],
            invalidRows: (int) $values['invalidRows'],
            uniqueDocuments: (int) $values['uniqueDocuments'],
            uniquePhones: (int) $values['uniquePhones'],
            duplicateDocumentPhones: (int) $values['duplicateDocumentPhones'],
            invalidDocuments: (int) ($values['invalidDocuments'] ?? 0),
            invalidPhones: (int) $values['invalidPhones'],
            invalidOperators: (int) $values['invalidOperators'],
            ambiguousOperators: (int) ($values['ambiguousOperators'] ?? 0),
            invalidDates: (int) $values['invalidDates'],
            emptyRows: (int) $values['emptyRows'],
            missingHeaders: (int) $values['missingHeaders'],
            extraHeaders: (int) $values['extraHeaders'],
            estimatedScope: (int) $values['estimatedScope'],
            totalErrors: (int) $values['totalErrors'],
            errors: array_values($values['errors']),
            warningsTotal: (int) ($values['warningsTotal'] ?? 0),
            warnings: array_values($values['warnings'] ?? []),
            metrics: array_map(static fn (mixed $value): int => (int) $value, $values['metrics'] ?? []),
        );
    }
}
