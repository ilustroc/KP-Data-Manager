<?php

namespace Tests\Feature\Imports;

use App\DatasetCode;
use App\ImportType;
use App\Models\User;
use App\RefreshMode;
use App\SearchSourceCode;
use App\Services\Imports\ImportColumnMappingService;
use App\Services\Imports\ImportScopeDocumentService;
use App\Services\Imports\SearchDatasetCatalogService;
use App\Services\Imports\SearchImportConfigurationException;
use App\Services\Imports\SearchSourceCatalogService;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;

class SearchImportInfrastructureTest extends ImportFeatureTestCase
{
    public function test_active_datasets_are_ordered_and_disabled_dataset_is_rejected(): void
    {
        $this->insertDataset(DatasetCode::Telefonos, 'Teléfonos', 20);
        $this->insertDataset(DatasetCode::Personas, 'Personas', 10);
        $this->insertDataset(DatasetCode::Familia, 'Familia', 30, false);

        $service = app(SearchDatasetCatalogService::class);
        $activeCodes = $service->active()->pluck('dataset_code')->all();

        $this->assertSame(['PERSONAS', 'TELEFONOS'], $activeCodes);
        $this->expectException(SearchImportConfigurationException::class);
        $service->requireActive(DatasetCode::Familia);
    }

    public function test_source_catalog_allows_only_configured_refresh_modes(): void
    {
        $this->insertDataset(DatasetCode::Telefonos, 'Teléfonos', 20);
        $this->insertSource('FUENTE_PRUEBA', 'Fuente de prueba');
        $this->insertDatasetSource(
            DatasetCode::Telefonos,
            'FUENTE_PRUEBA',
            allowsScopeReplace: true,
        );
        $service = app(SearchSourceCatalogService::class);
        $source = SearchSourceCode::from('fuente_prueba');

        $definition = $service->requireAllowed(
            DatasetCode::Telefonos,
            $source,
            RefreshMode::ScopeReplace,
        );

        $this->assertSame('FUENTE_PRUEBA', $definition->source_code);
        $this->assertCount(1, $service->activeForDataset(DatasetCode::Telefonos));

        $this->expectException(SearchImportConfigurationException::class);
        $service->requireAllowed(DatasetCode::Telefonos, $source, RefreshMode::Upsert);
    }

    public function test_source_catalog_rejects_upsert_outside_base_telefonos_even_when_flag_is_enabled(): void
    {
        $this->insertDataset(DatasetCode::Personas, 'Personas', 10);
        $this->insertSource('BASE_PERSONAS', 'Base Personas');
        $this->insertDatasetSource(
            DatasetCode::Personas,
            'BASE_PERSONAS',
            allowsUpsert: true,
        );

        $visibleSource = app(SearchSourceCatalogService::class)
            ->activeForDataset(DatasetCode::Personas)
            ->first();

        $this->assertSame(0, $visibleSource->allows_upsert);

        $this->expectException(SearchImportConfigurationException::class);

        app(SearchSourceCatalogService::class)->requireAllowed(
            DatasetCode::Personas,
            SearchSourceCode::from('BASE_PERSONAS'),
            RefreshMode::Upsert,
        );
    }

    public function test_current_mapping_is_resolved_in_source_position_order(): void
    {
        $this->insertDataset(DatasetCode::Personas, 'Personas', 10);
        $this->insertSource('RENIEC', 'RENIEC');
        $this->insertDatasetSource(
            DatasetCode::Personas,
            'RENIEC',
            allowsFullReplace: true,
            mappingVersion: 2,
        );
        DB::connection('sqlite')->table('import_column_mapping')->insert([
            $this->mappingRow(2, 'Nombres', 'nombres', 2),
            $this->mappingRow(1, 'DNI', 'documento', 2),
        ]);

        $mappings = app(ImportColumnMappingService::class)->current(
            DatasetCode::Personas,
            SearchSourceCode::from('RENIEC'),
        );

        $this->assertSame([1, 2], $mappings->pluck('source_position')->all());
        $this->assertSame(['documento', 'nombres'], $mappings->pluck('target_column')->all());
    }

    public function test_scope_replacement_preserves_text_identifiers_and_is_idempotent(): void
    {
        $batchId = $this->createBatch([
            'tipo' => ImportType::Search->value,
            'dataset_code' => DatasetCode::Telefonos->value,
            'source_code' => 'FUENTE_PRUEBA',
            'refresh_mode' => RefreshMode::ScopeReplace->value,
        ]);
        $service = app(ImportScopeDocumentService::class);

        $firstCount = $service->replaceForBatch($batchId, [
            ' 00003862 ',
            '48764435',
            '00003862',
            '47903198',
        ]);
        $secondCount = $service->replaceForBatch($batchId, [
            '00003862',
            '48764435',
            '47903198',
        ]);

        $documents = DB::connection('sqlite')
            ->table('import_scope_document')
            ->where('batch_id', $batchId)
            ->orderBy('documento')
            ->pluck('documento')
            ->all();

        $this->assertSame(3, $firstCount);
        $this->assertSame(3, $secondCount);
        $this->assertSame(['00003862', '47903198', '48764435'], $documents);
        $this->assertSame(3, $this->batchRow($batchId)->scope_count);
    }

    public function test_invalid_scope_rolls_back_without_losing_previous_documents(): void
    {
        $batchId = $this->createBatch(['tipo' => ImportType::Search->value]);
        $service = app(ImportScopeDocumentService::class);
        $service->replaceForBatch($batchId, ['00003862']);

        try {
            $service->replaceForBatch($batchId, ['48764435', '']);
            $this->fail('El documento vacío debió rechazar el scope.');
        } catch (SearchImportConfigurationException) {
            $documents = DB::connection('sqlite')
                ->table('import_scope_document')
                ->where('batch_id', $batchId)
                ->pluck('documento')
                ->all();

            $this->assertSame(['00003862'], $documents);
            $this->assertSame(1, $this->batchRow($batchId)->scope_count);
        }
    }

    public function test_search_preview_is_exposed_but_generic_registration_still_rejects_search(): void
    {
        config(['imports.registration_types' => ['PAGOS', 'CARTERA', 'SEARCH']]);
        Queue::fake();
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->get(route('imports.create'))
            ->assertOk()
            ->assertSee('KP Search');

        $this->actingAs($user)
            ->from(route('imports.create'))
            ->post(route('imports.store'), [
                'tipo' => ImportType::Search->value,
                'origen' => 'MANUAL',
                'archivo' => $this->validCsv(),
            ])
            ->assertInvalid('archivo');

        $this->assertDatabaseCount('import_batch', 0);
        Queue::assertNothingPushed();
    }

    private function insertDataset(
        DatasetCode $dataset,
        string $label,
        int $sortOrder,
        bool $active = true,
    ): void {
        DB::connection('sqlite')->table('import_dataset')->insert([
            'dataset_code' => $dataset->value,
            'label' => $label,
            'description' => null,
            'sort_order' => $sortOrder,
            'is_active' => $active,
            'created_at' => '2026-10-14 12:00:00',
            'updated_at' => '2026-10-14 12:00:00',
        ]);
    }

    private function insertSource(string $sourceCode, string $label): void
    {
        DB::connection('sqlite')->table('import_source')->insert([
            'source_code' => $sourceCode,
            'label' => $label,
            'description' => null,
            'is_active' => true,
            'created_at' => '2026-10-14 12:00:00',
            'updated_at' => '2026-10-14 12:00:00',
        ]);
    }

    private function insertDatasetSource(
        DatasetCode $dataset,
        string $sourceCode,
        bool $allowsFullReplace = false,
        bool $allowsScopeReplace = false,
        bool $allowsUpsert = false,
        ?int $mappingVersion = null,
    ): void {
        DB::connection('sqlite')->table('import_dataset_source')->insert([
            'dataset_code' => $dataset->value,
            'source_code' => $sourceCode,
            'default_refresh_mode' => RefreshMode::FullReplace->value,
            'allows_full_replace' => $allowsFullReplace,
            'allows_scope_replace' => $allowsScopeReplace,
            'allows_upsert' => $allowsUpsert,
            'current_mapping_version' => $mappingVersion,
            'is_active' => true,
            'created_at' => '2026-10-14 12:00:00',
            'updated_at' => '2026-10-14 12:00:00',
        ]);
    }

    /**
     * @return array<string, mixed>
     */
    private function mappingRow(
        int $position,
        string $sourceColumn,
        string $targetColumn,
        int $version,
    ): array {
        return [
            'dataset_code' => DatasetCode::Personas->value,
            'source_code' => 'RENIEC',
            'mapping_version' => $version,
            'source_position' => $position,
            'source_column' => $sourceColumn,
            'target_column' => $targetColumn,
            'is_required' => true,
            'transformation' => null,
            'default_value' => null,
            'is_active' => true,
            'created_at' => '2026-10-14 12:00:00',
            'updated_at' => '2026-10-14 12:00:00',
        ];
    }
}
