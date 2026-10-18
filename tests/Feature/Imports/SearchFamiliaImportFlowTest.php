<?php

namespace Tests\Feature\Imports;

use App\Jobs\ProcessImportBatch;
use App\Models\User;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;

class SearchFamiliaImportFlowTest extends ImportFeatureTestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config([
            'imports.search.registration_enabled' => true,
            'imports.search.available_datasets' => ['FAMILIA'],
        ]);
        $now = '2026-10-16 12:00:00';
        DB::connection('sqlite')->table('import_dataset')->insert([
            'dataset_code' => 'FAMILIA',
            'label' => 'Familia',
            'description' => null,
            'sort_order' => 30,
            'is_active' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::connection('sqlite')->table('import_source')->insert([
            'source_code' => 'BASE_FAMILIA',
            'label' => 'Base Familia',
            'description' => null,
            'is_active' => 1,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::connection('sqlite')->table('import_dataset_source')->insert([
            'dataset_code' => 'FAMILIA',
            'source_code' => 'BASE_FAMILIA',
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

    public function test_preview_and_confirmation_preserve_the_family_source_contract_without_business_warnings(): void
    {
        Storage::fake('imports');
        Queue::fake();
        $user = User::factory()->operator()->create();

        $response = $this->actingAs($user)->post(route('imports.search.preview'), [
            'dataset_code' => 'FAMILIA',
            'source_code' => 'BASE_FAMILIA',
            'refresh_mode' => 'SCOPE_REPLACE',
            'archivo' => UploadedFile::fake()->createWithContent(
                'familia.csv',
                "DOCUMENTO,DOCUMENTO FAM.,PATERNO FAM.,MATERNO FAM.,NOMBRES FAM.,NACIMIENTO FAM.,TIPO FAM.\n"
                ."09529768,9406251AN,ARANA,RAMOS,LUIS ALBERTO,22/03/1994,H\n"
                ."09529768,0,,,,,VALOR NO CATALOGADO\n",
            ),
        ]);

        $response->assertRedirect();
        $this->assertDatabaseCount('import_batch', 0);
        Queue::assertNothingPushed();
        $token = basename((string) $response->headers->get('Location'));

        $this->actingAs($user)
            ->get(route('imports.search.preview.show', $token))
            ->assertOk()
            ->assertSee('Preview FAMILIA')
            ->assertSee('DOCUMENTO FAM.')
            ->assertSee('9406251AN')
            ->assertSee('VALOR NO CATALOGADO');

        $this->actingAs($user)->post(route('imports.search.confirm'), [
            'token' => $token,
            'mapping' => $this->mapping(),
            'confirmacion' => '1',
        ])->assertRedirect();

        $batch = DB::connection('sqlite')->table('import_batch')->first();
        $this->assertSame('FAMILIA', $batch->dataset_code);
        $this->assertSame('BASE_FAMILIA', $batch->source_code);
        $this->assertSame('SCOPE_REPLACE', $batch->refresh_mode);
        $this->assertSame(7, DB::connection('sqlite')->table('import_column_mapping')->count());
        Queue::assertPushed(ProcessImportBatch::class);
    }

    /** @return array<string, string> */
    private function mapping(): array
    {
        return [
            'documento' => 'DOCUMENTO',
            'documento_familiar' => 'DOCUMENTO FAM.',
            'paterno_familiar' => 'PATERNO FAM.',
            'materno_familiar' => 'MATERNO FAM.',
            'nombres_familiar' => 'NOMBRES FAM.',
            'nacimiento_familiar' => 'NACIMIENTO FAM.',
            'tipo_familiar' => 'TIPO FAM.',
        ];
    }
}
