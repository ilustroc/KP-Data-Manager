<?php

namespace App\Services\Imports;

use App\DatasetCode;

final readonly class SearchImportDefinitionRegistry
{
    public function __construct(
        private PersonasImportDefinition $personas,
        private TelefonosImportDefinition $telefonos,
        private CorreosImportDefinition $correos,
        private DireccionesImportDefinition $direcciones,
        private VehiculosImportDefinition $vehiculos,
        private PropiedadesImportDefinition $propiedades,
        private SbsResumenImportDefinition $sbsResumen,
        private SbsDetalleImportDefinition $sbsDetalle,
        private LaboralEssaludImportDefinition $laboralEssalud,
    ) {}

    public function resolve(DatasetCode $dataset): SearchImportDefinition
    {
        return match ($dataset) {
            DatasetCode::Personas => $this->personas,
            DatasetCode::Telefonos => $this->telefonos,
            DatasetCode::Correos => $this->correos,
            DatasetCode::Direcciones => $this->direcciones,
            DatasetCode::Vehiculos => $this->vehiculos,
            DatasetCode::Propiedades => $this->propiedades,
            DatasetCode::SbsResumen => $this->sbsResumen,
            DatasetCode::SbsDetalle => $this->sbsDetalle,
            DatasetCode::LaboralEssalud => $this->laboralEssalud,
            default => throw new SearchImportConfigurationException(
                "El dataset {$dataset->value} todavía no está disponible para carga.",
            ),
        };
    }
}
