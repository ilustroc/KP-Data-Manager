<?php

namespace Tests\Unit;

use App\DatasetCode;
use App\Services\Imports\SearchDmf5Contract;
use App\Services\Imports\SearchImportDefinitionRegistry;
use Tests\TestCase;

class SearchFinancialImportDefinitionTest extends TestCase
{
    public function test_financial_datasets_resolve_with_their_exact_source_headers(): void
    {
        $definitions = $this->app->make(SearchImportDefinitionRegistry::class);

        $this->assertSame(
            ['COD_SBS', 'FECHA_REPORTE_SBS', 'DOCUMENTO', 'CANTIDAD_EMPRESAS', 'CALIFICACION_NORMAL', 'CALIFICACION_CPP', 'CALIFICACION_DEFICIENTE', 'CALIFICACION_DUDOSO', 'CALIFICACION_PERDIDAD'],
            $definitions->resolve(DatasetCode::SbsResumen)->expectedHeaders(),
        );
        $this->assertSame(
            ['FECHA_REPORTE_SBS', 'DOCUMENTO', 'COD_SBS', 'ENTIDAD', 'TIPO_CREDITO', 'CONDICION', 'MONTO', 'DIAS_ATRASO'],
            $definitions->resolve(DatasetCode::SbsDetalle)->expectedHeaders(),
        );
        $this->assertSame(
            ['DOCUMENTO', 'FECHA', 'RUC', 'NOMBRE EMPRESA', 'SUELDO', 'SITUACION'],
            $definitions->resolve(DatasetCode::LaboralEssalud)->expectedHeaders(),
        );
    }

    public function test_shared_contract_exposes_the_closed_sbs_condition_catalog(): void
    {
        $contract = $this->app->make(SearchDmf5Contract::class);

        $this->assertSame(['NOR', 'CPP', 'DEF', 'DUD', 'PER'], $contract->sbsConditions());
    }
}
