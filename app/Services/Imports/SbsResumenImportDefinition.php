<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class SbsResumenImportDefinition implements SearchImportDefinition
{
    public function dataset(): DatasetCode
    {
        return DatasetCode::SbsResumen;
    }

    public function label(): string
    {
        return 'SBS resumen';
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
        return ['cod_sbs' => 'Código SBS', 'fecha_reporte_sbs' => 'Periodo SBS', 'documento' => 'Documento', 'cantidad_empresas' => 'Cantidad empresas', 'calificacion_normal' => 'Calificación normal', 'calificacion_cpp' => 'Calificación CPP', 'calificacion_deficiente' => 'Calificación deficiente', 'calificacion_dudoso' => 'Calificación dudoso', 'calificacion_perdida' => 'Calificación pérdida'];
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
        return ['COD_SBS', 'FECHA_REPORTE_SBS', 'DOCUMENTO', 'CANTIDAD_EMPRESAS', 'CALIFICACION_NORMAL', 'CALIFICACION_CPP', 'CALIFICACION_DEFICIENTE', 'CALIFICACION_DUDOSO', 'CALIFICACION_PERDIDAD'];
    }

    public function suggest(array $headers): array
    {
        return array_filter(array_combine(array_keys($this->fields()), $this->expectedHeaders()), static fn (string $header): bool => in_array($header, $headers, true));
    }
}
