<?php

namespace App\Services\Reports;

class StoredManagementHistoryReport
{
    public function __construct(
        public readonly string $fileId,
        public readonly string $filename,
        public readonly string $webViewLink,
        public readonly int $sizeBytes,
    ) {}
}
