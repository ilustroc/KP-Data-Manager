<?php

namespace App\Services\Imports;

use App\DatasetCode;

final readonly class SearchImportDefinitionRegistry
{
    public function __construct(
        private PersonasImportDefinition $personas,
        private TelefonosImportDefinition $telefonos,
    ) {}

    public function resolve(DatasetCode $dataset): SearchImportDefinition
    {
        return match ($dataset) {
            DatasetCode::Personas => $this->personas,
            DatasetCode::Telefonos => $this->telefonos,
            default => throw new SearchImportConfigurationException(
                "El dataset {$dataset->value} todavía no está disponible para carga.",
            ),
        };
    }
}
