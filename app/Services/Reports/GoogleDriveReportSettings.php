<?php

namespace App\Services\Reports;

readonly class GoogleDriveReportSettings
{
    public function __construct(
        public string $credentialsPath,
        public string $folderId,
        public ?string $sharedDriveId,
        public string $filename,
        public int $chunkSizeBytes,
    ) {}
}
