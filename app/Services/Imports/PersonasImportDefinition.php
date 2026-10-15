<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;

final class PersonasImportDefinition implements SearchImportDefinition
{
    public const PROFILE_VERSION = '1';

    public function dataset(): DatasetCode
    {
        return DatasetCode::Personas;
    }

    public function label(): string
    {
        return 'Personas';
    }

    public function profileVersion(): string
    {
        return self::PROFILE_VERSION;
    }

    public function refreshModes(): array
    {
        return [RefreshMode::FullReplace, RefreshMode::ScopeReplace];
    }

    /** @return list<string> */
    public function expectedHeaders(): array
    {
        return [
            'DOCUMENTO',
            'PATERNO',
            'MATERNO',
            'NOMBRES',
            'NACIMIENTO',
            'DIRECCION',
            'SEXO',
            'ESTADO CIVIL',
            'PADRE',
            'MADRE',
        ];
    }

    /** @return array<string, string> */
    public function fields(): array
    {
        return [
            'documento' => 'Documento',
            'paterno' => 'Apellido paterno',
            'materno' => 'Apellido materno',
            'nombres' => 'Nombres',
            'fecha_nacimiento' => 'Fecha de nacimiento',
            'direccion_origen' => 'Dirección de origen',
            'sexo' => 'Sexo (código fuente)',
            'estado_civil' => 'Estado civil',
            'padre' => 'Padre',
            'madre' => 'Madre',
        ];
    }

    public function requiredFields(): array
    {
        return array_keys($this->fields());
    }

    public function requiresFullPreviewAnalysis(): bool
    {
        return false;
    }

    /** @return array<string, list<string>> */
    public function aliases(): array
    {
        return [
            'documento' => ['DOCUMENTO', 'DNI'],
            'paterno' => ['PATERNO', 'APELLIDO PATERNO'],
            'materno' => ['MATERNO', 'APELLIDO MATERNO'],
            'nombres' => ['NOMBRES', 'NOMBRE'],
            'fecha_nacimiento' => ['NACIMIENTO', 'FECHA NACIMIENTO', 'FECHA DE NACIMIENTO'],
            'direccion_origen' => ['DIRECCION', 'DIRECCIÓN'],
            'sexo' => ['SEXO'],
            'estado_civil' => ['ESTADO CIVIL'],
            'padre' => ['PADRE'],
            'madre' => ['MADRE'],
        ];
    }

    /**
     * @param  list<string>  $headers
     * @return array<string, string>
     */
    public function suggest(array $headers): array
    {
        $normalizedHeaders = [];
        foreach ($headers as $header) {
            $normalizedHeaders[$this->normalizeHeader($header)] = $header;
        }

        $mapping = [];
        foreach ($this->aliases() as $target => $aliases) {
            foreach ($aliases as $alias) {
                $source = $normalizedHeaders[$this->normalizeHeader($alias)] ?? null;
                if ($source !== null) {
                    $mapping[$target] = $source;
                    break;
                }
            }
        }

        return $mapping;
    }

    private function normalizeHeader(string $header): string
    {
        return mb_strtoupper((string) preg_replace('/\s+/u', ' ', trim(str_replace("\u{00A0}", ' ', $header))));
    }
}
