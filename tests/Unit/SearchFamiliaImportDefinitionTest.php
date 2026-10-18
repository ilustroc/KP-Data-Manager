<?php

namespace Tests\Unit;

use App\DatasetCode;
use App\RefreshMode;
use App\Services\Imports\SearchImportDefinitionRegistry;
use Tests\TestCase;

class SearchFamiliaImportDefinitionTest extends TestCase
{
    public function test_familia_resolves_with_the_exact_historical_source_headers(): void
    {
        $definition = $this->app->make(SearchImportDefinitionRegistry::class)
            ->resolve(DatasetCode::Familia);

        $this->assertSame(
            [
                'DOCUMENTO',
                'DOCUMENTO FAM.',
                'PATERNO FAM.',
                'MATERNO FAM.',
                'NOMBRES FAM.',
                'NACIMIENTO FAM.',
                'TIPO FAM.',
            ],
            $definition->expectedHeaders(),
        );
        $this->assertSame(
            [RefreshMode::FullReplace, RefreshMode::ScopeReplace],
            $definition->refreshModes(),
        );
        $this->assertFalse($definition->requiresFullPreviewAnalysis());
    }
}
