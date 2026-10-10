<?php

namespace App\Services\Reports;

readonly class GoogleDriveReportAccessSettings
{
    public function __construct(
        public string $credentialsPath,
        public string $folderId,
        public ?string $sharedDriveId,
    ) {}
}
