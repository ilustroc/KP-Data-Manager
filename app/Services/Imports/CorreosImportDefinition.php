<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class CorreosImportDefinition implements SearchImportDefinition
{
    public function dataset(): DatasetCode
    {
        return DatasetCode::Correos;
    }

    public function label(): string
    {
        return 'Correos';
    }

    public function profileVersion(): string
    {
        return '1';
    }

    public function refreshModes(): array
    {
        return [RefreshMode::FullReplace, RefreshMode::ScopeReplace];
    }

    public function fields(): array
    {
        return ['documento' => 'Documento', 'correo_original' => 'Correo original'];
    }

    public function requiredFields(): array
    {
        return array_keys($this->fields());
    }

    public function aliases(): array
    {
        return ['documento' => ['DOCUMENTO'], 'correo_original' => ['CORREO_ORIGINAL']];
    }

    public function requiresFullPreviewAnalysis(): bool
    {
        return true;
    }

    public function expectedHeaders(): array
    {
        return ['DOCUMENTO', 'CORREO_ORIGINAL'];
    }

    public function suggest(array $headers): array
    {
        return $this->mapHeaders($headers);
    }

    /** @param list<string> $headers @return array<string, string> */
    private function mapHeaders(array $headers): array
    {
        return array_filter(array_combine(array_keys($this->fields()), $this->expectedHeaders()), static fn (string $header): bool => in_array($header, $headers, true));
    }
}
