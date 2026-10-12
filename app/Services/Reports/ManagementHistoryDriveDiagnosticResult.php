<?php

namespace App\Services\Reports;

readonly class ManagementHistoryDriveDiagnosticResult
{
    public function __construct(
        public bool $sharedDriveConfigured,
    ) {}
}
