<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class FamiliaImportDefinition implements SearchImportDefinition
{
    public function dataset(): DatasetCode
    {
        return DatasetCode::Familia;
    }

    public function label(): string
    {
        return 'Familia';
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
        return [
            'documento' => 'Documento titular',
            'documento_familiar' => 'Documento familiar',
            'paterno_familiar' => 'Apellido paterno familiar',
            'materno_familiar' => 'Apellido materno familiar',
            'nombres_familiar' => 'Nombres familiar',
            'nacimiento_familiar' => 'Nacimiento familiar',
            'tipo_familiar' => 'Tipo familiar',
        ];
    }

    public function requiredFields(): array
    {
        return array_keys($this->fields());
    }

    public function aliases(): array
    {
        return array_combine(
            array_keys($this->fields()),
            array_map(static fn (string $header): array => [$header], $this->expectedHeaders()),
        );
    }

    public function requiresFullPreviewAnalysis(): bool
    {
        return false;
    }

    public function expectedHeaders(): array
    {
        return [
            'DOCUMENTO',
            'DOCUMENTO FAM.',
            'PATERNO FAM.',
            'MATERNO FAM.',
            'NOMBRES FAM.',
            'NACIMIENTO FAM.',
            'TIPO FAM.',
        ];
    }

    public function suggest(array $headers): array
    {
        return array_filter(
            array_combine(array_keys($this->fields()), $this->expectedHeaders()),
            static fn (string $header): bool => in_array($header, $headers, true),
        );
    }
}
