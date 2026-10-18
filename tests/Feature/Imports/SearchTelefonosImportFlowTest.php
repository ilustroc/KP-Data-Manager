<?php

namespace Tests\Feature\Imports;

use App\Jobs\ProcessImportBatch;
use App\Models\User;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\Storage;

class SearchTelefonosImportFlowTest extends ImportFeatureTestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config([
            'imports.search.registration_enabled' => true,
            'imports.search.available_datasets' => ['PERSONAS', 'TELEFONOS'],
        ]);
        $now = '2026-10-15 12:00:00';
        DB::connection('sqlite')->table('import_dataset')->insert([
            'dataset_code' => 'TELEFONOS', 'label' => 'Teléfonos', 'description' => null,
            'sort_order' => 20, 'is_active' => 1, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::connection('sqlite')->table('import_source')->insert([
            'source_code' => 'BASE_TELEFONOS', 'label' => 'Base Teléfonos', 'description' => null,
            'is_active' => 1, 'created_at' => $now, 'updated_at' => $now,
        ]);
        DB::connection('sqlite')->table('import_dataset_source')->insert([
            'dataset_code' => 'TELEFONOS', 'source_code' => 'BASE_TELEFONOS',
            'default_refresh_mode' => 'FULL_REPLACE', 'allows_full_replace' => 1,
            'allows_scope_replace' => 1, 'allows_upsert' => 0,
            'current_mapping_version' => null, 'is_active' => 1,
            'created_at' => $now, 'updated_at' => $now,
        ]);
        Schema::connection('sqlite')->dropIfExists('search_telefonos_gold');
        Schema::connection('sqlite')->dropIfExists('search_telefonos');
        Schema::connection('sqlite')->create('search_telefonos', function (Blueprint $table): void {
            $table->id('phone_id');
        });
        Schema::connection('sqlite')->create('search_telefonos_gold', function (Blueprint $table): void {
            $table->string('documento', 20);
        });
    }

    public function test_valid_preview_scans_the_whole_file_without_creating_a_batch_and_can_be_confirmed(): void
    {
        Storage::fake('imports');
        Queue::fake();
        $user = User::factory()->operator()->create();

        $response = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(
            "DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n".
            "00003862,934043966,MOVISTAR NOVIEMBRE 2024,2024-11-01\n".
            "00009743,951159659,ENTEL JULIO 2026,2026-07-02\n",
        ));

        $response->assertRedirect();
        $this->assertDatabaseCount('import_batch', 0);
        Queue::assertNothingPushed();
        $token = basename((string) $response->headers->get('Location'));
        $this->actingAs($user)->get(route('imports.search.preview.show', $token))
            ->assertOk()
            ->assertSee('Preview TELEFONOS')
            ->assertSee('Archivo listo para procesar')
            ->assertSee('MOVISTAR NOVIEMBRE 2024')
            ->assertDontSee('Resumen de errores');
        $this->assertDatabaseCount('import_batch', 0);
        $this->assertDatabaseCount('import_scope_document', 0);

        $this->actingAs($user)->post(route('imports.search.confirm'), [
            'token' => $token,
            'mapping' => $this->mapping(),
            'confirmacion' => '1',
        ])->assertRedirect();

        $batch = DB::connection('sqlite')->table('import_batch')->first();
        $this->assertSame('TELEFONOS', $batch->dataset_code);
        $this->assertSame('BASE_TELEFONOS', $batch->source_code);
        $this->assertSame('HISTORICO', $batch->origen);
        $this->assertSame('1', $batch->perfil_version);
        $this->assertSame(4, DB::connection('sqlite')->table('import_column_mapping')->count());
        $this->assertSame(
            ['TELEFONOS_V1'],
            DB::connection('sqlite')->table('import_column_mapping')->distinct()->pluck('transformation')->all(),
        );
        Queue::assertPushed(ProcessImportBatch::class);
        $this->actingAs($user)->get(route('imports.show', $batch->batch_id))
            ->assertOk()
            ->assertDontSee('Histórico');
    }

    public function test_invalid_preview_blocks_confirmation_and_does_not_write_persistent_search_data(): void
    {
        Storage::fake('imports');
        Queue::fake();
        $user = User::factory()->operator()->create();
        $response = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(
            "DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n".
            "00003862,911111111,DESCONOCIDO,fecha\n",
        ));
        $token = basename((string) $response->headers->get('Location'));

        $this->actingAs($user)->get(route('imports.search.preview.show', $token))
            ->assertOk()
            ->assertSee('Archivo no apto para procesar')
            ->assertSee('PHONE_INVALID')
            ->assertSee('El teléfono debe contener exactamente 9 dígitos, comenzar con 9 y superar las reglas de coherencia.')
            ->assertSee('OPERATOR_INVALID')
            ->assertSee('No se reconoció un operador permitido.')
            ->assertSee('DATE_INVALID')
            ->assertSee('disabled', false);

        $this->actingAs($user)->from(route('imports.search.preview.show', $token))
            ->post(route('imports.search.confirm'), [
                'token' => $token,
                'mapping' => $this->mapping(),
                'confirmacion' => '1',
            ])
            ->assertRedirect(route('imports.search.preview.show', $token))
            ->assertSessionHasErrors('mapping');

        $this->assertDatabaseCount('import_batch', 0);
        $this->assertDatabaseCount('import_scope_document', 0);
        Queue::assertNothingPushed();
    }

    public function test_error_preview_shows_summary_and_downloads_the_complete_private_csv_without_creating_search_data(): void
    {
        Storage::fake('imports');
        Queue::fake();
        $user = User::factory()->operator()->create();
        $response = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(
            "DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n".
            "123,934043966,CLARO,2026-01-01\n".
            "00003862,911111111,CLARO,2026-01-01\n".
            "00009743,934043966,CLARO,fecha\n".
            "00009826,951159659,CLARO,2026-01-01\n".
            "00009826,951159659,CLARO,2026-01-02\n".
            "00009827,934043966,OPERADOR INVENTADO,2026-01-01\n".
            "00009828,934043966,MOVISTAR CLARO 2026,2026-01-01\n",
        ));
        $token = basename((string) $response->headers->get('Location'));

        $this->actingAs($user)->get(route('imports.search.preview.show', $token))
            ->assertOk()
            ->assertSee('Resumen de errores')
            ->assertSee('Fechas inválidas')
            ->assertSee('Teléfonos inválidos')
            ->assertSee('Documentos inválidos')
            ->assertSee('Duplicados')
            ->assertSee('Descargar errores')
            ->assertSee('disabled', false);

        $download = $this->actingAs($user)->get(route('imports.search.preview.errors', $token));
        $download->assertOk()
            ->assertHeader('content-type', 'text/csv; charset=UTF-8')
            ->assertHeader('x-content-type-options', 'nosniff');
        $contents = $download->streamedContent();
        $this->assertStringStartsWith("\xEF\xBB\xBF", $contents);
        $this->assertStringContainsString('FILA,DOCUMENTO,TELEFONO,CAMPO,CODIGO_ERROR,DESCRIPCION,VALOR_ORIGINAL', $contents);
        $this->assertStringContainsString('DOCUMENT_INVALID,"DNI debe contener exactamente 8 dígitos."', $contents);
        $this->assertStringContainsString('PHONE_INVALID,"El teléfono debe contener exactamente 9 dígitos, comenzar con 9 y superar las reglas de coherencia."', $contents);
        $this->assertStringContainsString('DATE_INVALID,"FECHA DATA no contiene una fecha válida."', $contents);
        $this->assertStringContainsString('DUPLICATE_DOCUMENT_PHONE,"La combinación DOCUMENTO + TELEFONO está repetida dentro del archivo."', $contents);
        $this->assertStringContainsString('OPERATOR_INVALID,"No se reconoció un operador permitido."', $contents);
        $this->assertStringContainsString('OPERATOR_AMBIGUOUS,"Se detectó más de un operador permitido."', $contents);
        $this->assertStringContainsString('00009826,951159659,telefono,DUPLICATE_DOCUMENT_PHONE', $contents);
        $this->assertStringNotContainsString('mysql_', $contents);
        $this->assertStringNotContainsString('stacktrace', $contents);

        $this->assertDatabaseCount('import_batch', 0);
        $this->assertDatabaseCount('search_raw_row', 0);
        $this->assertDatabaseCount('search_telefonos', 0);
        $this->assertDatabaseCount('search_telefonos_gold', 0);
        $this->assertDatabaseCount('import_scope_document', 0);
        Queue::assertNothingPushed();
        Storage::disk('imports')->assertExists("search-previews/{$user->id}/{$token}.csv");
        $this->assertSame(["search-previews/{$user->id}/{$token}.csv"], Storage::disk('imports')->allFiles());
    }

    public function test_download_can_include_more_than_the_one_hundred_errors_rendered_by_the_preview(): void
    {
        Storage::fake('imports');
        $user = User::factory()->operator()->create();
        $rows = ['DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA'];
        for ($index = 1; $index <= 105; $index++) {
            $rows[] = str_pad((string) $index, 8, '0', STR_PAD_LEFT).',911111111,CLARO,2026-01-01';
        }

        $response = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(implode("\n", $rows)."\n"));
        $token = basename((string) $response->headers->get('Location'));

        $this->actingAs($user)->get(route('imports.search.preview.show', $token))
            ->assertSee('Primeros errores detectados (105)')
            ->assertSee('máximo 100 errores');

        $contents = $this->actingAs($user)
            ->get(route('imports.search.preview.errors', $token))
            ->streamedContent();
        $this->assertSame(105, substr_count($contents, 'PHONE_INVALID'));
    }

    public function test_preview_matches_operator_anywhere_and_blocks_ambiguous_values(): void
    {
        Storage::fake('imports');
        $user = User::factory()->operator()->create();

        $valid = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(
            "DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n".
            "00003862,934043966,SEPTIEMBRE MOVISTAR 2020,2026-01-01\n".
            "00009743,951159659,ENERO FLASH MOBILE 2026,2026-01-02\n",
        ));
        $this->actingAs($user)
            ->get(route('imports.search.preview.show', basename((string) $valid->headers->get('Location'))))
            ->assertOk()
            ->assertSee('Archivo listo para procesar');

        $ambiguous = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(
            "DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n".
            "00003862,934043966,MOVISTAR CLARO 2025,2026-01-01\n",
        ));
        $this->actingAs($user)
            ->get(route('imports.search.preview.show', basename((string) $ambiguous->headers->get('Location'))))
            ->assertOk()
            ->assertSee('OPERATOR_AMBIGUOUS')
            ->assertSee('Se detectó más de un operador permitido.')
            ->assertSee('Archivo no apto para procesar');
    }

    public function test_duplicate_pair_blocks_but_same_phone_for_distinct_documents_is_allowed(): void
    {
        Storage::fake('imports');
        $user = User::factory()->operator()->create();
        $duplicate = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(
            "DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n".
            "00003862,934043966,CLARO,2026-01-01\n".
            "00003862,934043966,CLARO,2026-01-02\n",
        ));
        $duplicateToken = basename((string) $duplicate->headers->get('Location'));
        $this->actingAs($user)->get(route('imports.search.preview.show', $duplicateToken))
            ->assertSee('DUPLICATE_DOCUMENT_PHONE')
            ->assertSee('Archivo no apto para procesar');

        $allowed = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(
            "DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n".
            "00003862,934043966,CLARO,2026-01-01\n".
            "00009743,934043966,CLARO,2026-01-02\n",
        ));
        $allowedToken = basename((string) $allowed->headers->get('Location'));
        $this->actingAs($user)->get(route('imports.search.preview.show', $allowedToken))
            ->assertSee('Archivo listo para procesar');
    }

    public function test_changed_mapping_is_reanalyzed_before_registration(): void
    {
        Storage::fake('imports');
        Queue::fake();
        $user = User::factory()->operator()->create();
        $response = $this->actingAs($user)->post(route('imports.search.preview'), $this->payload(
            "DOCUMENTO,TELEFONO,OPERADOR,FECHA DATA\n00003862,934043966,CLARO,2026-01-01\n",
        ));
        $token = basename((string) $response->headers->get('Location'));
        $changed = $this->mapping();
        $changed['telefono'] = 'DOCUMENTO';
        $changed['documento'] = 'TELEFONO';

        $this->actingAs($user)->post(route('imports.search.confirm'), [
            'token' => $token, 'mapping' => $changed, 'confirmacion' => '1',
        ])->assertSessionHasErrors('mapping');

        $this->assertDatabaseCount('import_batch', 0);
        Queue::assertNothingPushed();
    }

    /** @return array<string, mixed> */
    private function payload(string $csv): array
    {
        return [
            'dataset_code' => 'TELEFONOS', 'source_code' => 'BASE_TELEFONOS',
            'refresh_mode' => 'FULL_REPLACE',
            'archivo' => UploadedFile::fake()->createWithContent('telefonos.csv', $csv),
        ];
    }

    /** @return array<string, string> */
    private function mapping(): array
    {
        return [
            'documento' => 'DOCUMENTO', 'telefono' => 'TELEFONO',
            'operador_raw' => 'OPERADOR', 'fecha_data' => 'FECHA DATA',
        ];
    }
}
