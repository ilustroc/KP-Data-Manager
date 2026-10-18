<?php

namespace Tests\Feature\Imports;

use App\Jobs\ProcessImportBatch;
use App\Models\User;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;

class SearchPersonasImportFlowTest extends ImportFeatureTestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config(['imports.search.registration_enabled' => true]);
        $now = '2026-10-14 12:00:00';
        DB::connection('sqlite')->table('import_dataset')->insert([
            'dataset_code' => 'PERSONAS',
            'label' => 'Personas',
            'description' => null,
            'sort_order' => 10,
            'is_active' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::connection('sqlite')->table('import_source')->insert([
            'source_code' => 'BASE_PERSONAS',
            'label' => 'Base Personas (prueba)',
            'description' => null,
            'is_active' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::connection('sqlite')->table('import_dataset_source')->insert([
            'dataset_code' => 'PERSONAS',
            'source_code' => 'BASE_PERSONAS',
            'default_refresh_mode' => 'FULL_REPLACE',
            'allows_full_replace' => 1,
            'allows_scope_replace' => 1,
            'allows_upsert' => 0,
            'current_mapping_version' => null,
            'is_active' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
    }

    public function test_preview_suggests_mapping_and_confirmation_registers_batch_before_dispatch(): void
    {
        Storage::fake('imports');
        Queue::fake();
        $user = User::factory()->operator()->create();

        $response = $this->actingAs($user)->post(route('imports.search.preview'), [
            'dataset_code' => 'PERSONAS',
            'source_code' => 'BASE_PERSONAS',
            'refresh_mode' => 'FULL_REPLACE',
            'archivo' => $this->personasCsv(),
        ]);

        $response->assertRedirect();
        Queue::assertNothingPushed();
        $token = basename((string) $response->headers->get('Location'));
        $this->actingAs($user)
            ->get(route('imports.search.preview.show', $token))
            ->assertOk()
            ->assertSee('Preview PERSONAS')
            ->assertSee('DOCUMENTO')
            ->assertSee('NACIMIENTO');

        $this->actingAs($user)->post(route('imports.search.confirm'), [
            'token' => $token,
            'mapping' => $this->mapping(),
            'confirmacion' => '1',
        ])->assertRedirect();

        $batch = DB::connection('sqlite')->table('import_batch')->first();
        $this->assertSame('SEARCH', $batch->tipo);
        $this->assertSame('PERSONAS', $batch->dataset_code);
        $this->assertSame('BASE_PERSONAS', $batch->source_code);
        $this->assertSame('FULL_REPLACE', $batch->refresh_mode);
        $this->assertSame('HISTORICO', $batch->origen);
        $this->assertSame('PENDIENTE', $batch->estado);
        $this->assertSame(1, $batch->mapping_version);
        $this->assertSame(10, DB::connection('sqlite')->table('import_column_mapping')->count());
        Queue::assertPushed(ProcessImportBatch::class, fn (ProcessImportBatch $job): bool => $job->batchId === $batch->batch_id);
    }

    public function test_confirmation_rejects_duplicate_source_columns(): void
    {
        Storage::fake('imports');
        Queue::fake();
        $user = User::factory()->operator()->create();
        $response = $this->actingAs($user)->post(route('imports.search.preview'), [
            'dataset_code' => 'PERSONAS',
            'source_code' => 'BASE_PERSONAS',
            'refresh_mode' => 'SCOPE_REPLACE',
            'archivo' => $this->personasCsv(),
        ]);
        $token = basename((string) $response->headers->get('Location'));
        $mapping = $this->mapping();
        $mapping['madre'] = 'PADRE';

        $this->actingAs($user)->from(route('imports.search.preview.show', $token))
            ->post(route('imports.search.confirm'), [
                'token' => $token,
                'mapping' => $mapping,
                'confirmacion' => '1',
            ])
            ->assertRedirect(route('imports.search.preview.show', $token))
            ->assertSessionHasErrors('mapping');

        $this->assertDatabaseCount('import_batch', 0);
        Queue::assertNothingPushed();
    }

    public function test_manual_mapping_accepts_nonstandard_source_headers_after_explicit_confirmation(): void
    {
        Storage::fake('imports');
        Queue::fake();
        $user = User::factory()->operator()->create();
        $headers = ['DOC', 'AP1', 'AP2', 'NOM', 'FEC', 'DIR', 'SX', 'EC', 'P', 'M'];
        $file = UploadedFile::fake()->createWithContent(
            'personas-manual.csv',
            implode(',', $headers)."\n00003862,PEREZ,LOPEZ,ANA,2000-01-02,CALLE 1,2,SOLTERO,JUAN,MARIA\n",
        );
        $response = $this->actingAs($user)->post(route('imports.search.preview'), [
            'dataset_code' => 'PERSONAS',
            'source_code' => 'BASE_PERSONAS',
            'refresh_mode' => 'SCOPE_REPLACE',
            'archivo' => $file,
        ]);
        $token = basename((string) $response->headers->get('Location'));
        $manualMapping = array_combine(array_keys($this->mapping()), $headers);

        $this->actingAs($user)->post(route('imports.search.confirm'), [
            'token' => $token,
            'mapping' => $manualMapping,
            'confirmacion' => '1',
        ])->assertRedirect();

        $this->assertSame(
            $headers,
            DB::connection('sqlite')->table('import_column_mapping')
                ->orderBy('source_position')
                ->pluck('source_column')
                ->all(),
        );
        Queue::assertPushed(ProcessImportBatch::class);
    }

    private function personasCsv(): UploadedFile
    {
        return UploadedFile::fake()->createWithContent(
            'personas.csv',
            "DOCUMENTO,PATERNO,MATERNO,NOMBRES,NACIMIENTO,DIRECCION,SEXO,ESTADO CIVIL,PADRE,MADRE\n00003862,PEREZ,LOPEZ,ANA,2000-01-02,CALLE 1,2,SOLTERO,JUAN,MARIA\n",
        );
    }

    /** @return array<string, string> */
    private function mapping(): array
    {
        return [
            'documento' => 'DOCUMENTO',
            'paterno' => 'PATERNO',
            'materno' => 'MATERNO',
            'nombres' => 'NOMBRES',
            'fecha_nacimiento' => 'NACIMIENTO',
            'direccion_origen' => 'DIRECCION',
            'sexo' => 'SEXO',
            'estado_civil' => 'ESTADO CIVIL',
            'padre' => 'PADRE',
            'madre' => 'MADRE',
        ];
    }
}
