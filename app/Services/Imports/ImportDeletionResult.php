<?php

namespace App\Services\Imports;

readonly class ImportDeletionResult
{
    public function __construct(
        public int $batchId,
        public bool $fileDeleted,
        public ?string $warning,
    ) {}
}
