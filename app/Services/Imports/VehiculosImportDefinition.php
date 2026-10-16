<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class VehiculosImportDefinition implements SearchImportDefinition
{
    public function dataset(): DatasetCode
    {
        return DatasetCode::Vehiculos;
    }

    public function label(): string
    {
        return 'Vehículos';
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
        return ['documento' => 'Documento', 'nombre_completo_fuente' => 'Nombre completo', 'clase' => 'Clase', 'anio_compra' => 'Año compra', 'anio_fabricacion' => 'Año fabricación', 'marca' => 'Marca', 'placa_original' => 'Placa', 'numero_transferencias' => 'Número transferencias'];
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
        return ['DOCUMENTO', 'NOMBRE COMPLETO', 'CLASE', 'COMPRA', 'FABRICACION', 'MARCA', 'PLACA', '# TRANSFERENCIA'];
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
