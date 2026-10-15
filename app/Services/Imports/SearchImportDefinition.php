<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

interface SearchImportDefinition
{
    public function dataset(): DatasetCode;

    public function label(): string;

    public function profileVersion(): string;

    /** @return list<RefreshMode> */
    public function refreshModes(): array;

    /** @return array<string, string> */
    public function fields(): array;

    /** @return list<string> */
    public function requiredFields(): array;

    /** @return array<string, list<string>> */
    public function aliases(): array;

    public function requiresFullPreviewAnalysis(): bool;

    /** @return list<string> */
    public function expectedHeaders(): array;

    /**
     * @param  list<string>  $headers
     * @return array<string, string>
     */
    public function suggest(array $headers): array;
}
