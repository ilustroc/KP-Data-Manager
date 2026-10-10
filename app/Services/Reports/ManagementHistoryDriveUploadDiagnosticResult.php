<?php

namespace App\Services\Reports;

readonly class ManagementHistoryDriveUploadDiagnosticResult
{
    public function __construct(
        public bool $created,
        public bool $read,
        public bool $trashed,
        public ?bool $canTrash,
        public ?bool $canDelete,
    ) {}
}
