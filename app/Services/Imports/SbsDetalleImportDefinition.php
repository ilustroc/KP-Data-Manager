<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class SbsDetalleImportDefinition implements SearchImportDefinition
{
    public function dataset(): DatasetCode
    {
        return DatasetCode::SbsDetalle;
    }

    public function label(): string
    {
        return 'SBS detalle';
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
        return ['fecha_reporte_sbs' => 'Periodo SBS', 'documento' => 'Documento', 'cod_sbs' => 'Código SBS', 'entidad' => 'Entidad', 'tipo_credito' => 'Tipo de crédito', 'condicion' => 'Condición', 'monto' => 'Monto', 'dias_atraso' => 'Días de atraso'];
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
        return ['FECHA_REPORTE_SBS', 'DOCUMENTO', 'COD_SBS', 'ENTIDAD', 'TIPO_CREDITO', 'CONDICION', 'MONTO', 'DIAS_ATRASO'];
    }

    public function suggest(array $headers): array
    {
        return array_filter(array_combine(array_keys($this->fields()), $this->expectedHeaders()), static fn (string $header): bool => in_array($header, $headers, true));
    }
}
