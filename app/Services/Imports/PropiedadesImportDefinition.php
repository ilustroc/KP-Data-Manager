<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class PropiedadesImportDefinition implements SearchImportDefinition
{
    public function dataset(): DatasetCode
    {
        return DatasetCode::Propiedades;
    }

    public function label(): string
    {
        return 'Propiedades';
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
        return ['documento' => 'Documento', 'partida_registral' => 'Partida registral', 'zona_registral' => 'Zona registral', 'oficina' => 'Oficina'];
    }

    public function requiredFields(): array
    {
        return array_keys($this->fields());
    }

    public function aliases(): array
    {
        return array_combine(array_keys($this->fields()), array_map(static fn (string $header): array => [$header], $this->expectedHeaders()));
    }

    public function requiresFullPreviewAnalysis(): bool
    {
        return true;
    }

    public function expectedHeaders(): array
    {
        return ['DOCUMENTO', 'PARTIDA_REGISTRAL', 'ZONA_REGISTRAL', 'OFICINA'];
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
