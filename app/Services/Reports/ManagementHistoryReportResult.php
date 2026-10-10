<?php

namespace App\Services\Reports;

class ManagementHistoryReportResult
{
    public function __construct(
        public readonly ManagementHistoryReportPeriod $period,
        public readonly string $filename,
        public readonly int $recordCount,
        public readonly int $recipientCount,
    ) {}
}
