<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class TelefonosImportDefinition implements SearchImportDefinition
{
    public function dataset(): DatasetCode
    {
        return DatasetCode::Telefonos;
    }

    public function label(): string
    {
        return 'Teléfonos';
    }

    public function profileVersion(): string
    {
        return '1';
    }

    public function refreshModes(): array
    {
        return [RefreshMode::FullReplace, RefreshMode::ScopeReplace, RefreshMode::Upsert];
    }

    /** @return array<string, string> */
    public function fields(): array
    {
        return [
            'documento' => 'Documento',
            'telefono' => 'Teléfono',
            'operador_raw' => 'Operador / origen',
            'fecha_data' => 'Fecha data',
        ];
    }

    public function requiredFields(): array
    {
        return array_keys($this->fields());
    }

    public function aliases(): array
    {
        return [
            'documento' => ['DOCUMENTO'],
            'telefono' => ['TELEFONO'],
            'operador_raw' => ['OPERADOR'],
            'fecha_data' => ['FECHA DATA'],
        ];
    }

    public function requiresFullPreviewAnalysis(): bool
    {
        return true;
    }

    /** @return list<string> */
    public function expectedHeaders(): array
    {
        return ['DOCUMENTO', 'TELEFONO', 'OPERADOR', 'FECHA DATA'];
    }

    /**
     * @param  list<string>  $headers
     * @return array<string, string>
     */
    public function suggest(array $headers): array
    {
        $expected = array_combine(array_keys($this->fields()), $this->expectedHeaders());

        return array_filter(
            $expected,
            static fn (string $header): bool => in_array($header, $headers, true),
        );
    }
}
