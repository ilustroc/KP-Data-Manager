<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class LaboralEssaludImportDefinition implements SearchImportDefinition
{
    public function dataset(): DatasetCode
    {
        return DatasetCode::LaboralEssalud;
    }

    public function label(): string
    {
        return 'Laboral EsSalud';
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
        return ['documento' => 'Documento', 'periodo' => 'Periodo', 'ruc' => 'RUC', 'nombre_empresa' => 'Nombre empresa', 'sueldo' => 'Sueldo', 'situacion' => 'Situación'];
    }

    public function requiredFields(): array
    {
        return array_keys($this->fields());
    }

    public function aliases(): array
    {
        return array_map(static fn (string $header): array => [$header], array_combine(array_keys($this->fields()), $this->expectedHeaders()));
    }

    public function requiresFullPreviewAnalysis(): bool
    {
        return true;
    }

    public function expectedHeaders(): array
    {
        return ['DOCUMENTO', 'FECHA', 'RUC', 'NOMBRE EMPRESA', 'SUELDO', 'SITUACION'];
    }

    public function suggest(array $headers): array
    {
        return array_filter(array_combine(array_keys($this->fields()), $this->expectedHeaders()), static fn (string $header): bool => in_array($header, $headers, true));
    }
}
