<?php

namespace App\Services\Reports;

class ManagementHistoryExport
{
    public function __construct(
        public readonly string $path,
        public readonly string $filename,
        public readonly int $recordCount,
    ) {}
}
