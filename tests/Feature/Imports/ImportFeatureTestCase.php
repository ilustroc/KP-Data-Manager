<?php

namespace Tests\Feature\Imports;

use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;
use ZipArchive;

abstract class ImportFeatureTestCase extends TestCase
{
    use LazilyRefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();

        $this->withoutVite();
        config([
            'imports.connection' => 'sqlite',
            'imports.table' => 'import_batch',
            'imports.error_table' => 'import_error',
            'imports.storage_disk' => 'imports',
            'imports.private_files.enforce_before_dispatch' => false,
            'imports.private_files.etl_user' => null,
            'imports.private_files.shared_group' => null,
            'imports.private_files.file_mode' => 0640,
            'imports.private_files.directory_mode' => 02750,
            'imports.max_web_upload_mb' => 50,
            'imports.allowed_extensions' => ['csv', 'xlsx'],
            'imports.registration_types' => ['PAGOS', 'CARTERA'],
            'imports.search.control_connection' => 'sqlite',
            'imports.search.bronze_connection' => 'sqlite',
            'imports.search.scope_insert_chunk_size' => 2,
            'imports.search.tables' => [
                'datasets' => 'import_dataset',
                'sources' => 'import_source',
                'dataset_sources' => 'import_dataset_source',
                'column_mappings' => 'import_column_mapping',
                'scope_documents' => 'import_scope_document',
                'raw_rows' => 'search_raw_row',
            ],
            'imports.deletion.audit_table' => 'import_deletion_log',
            'imports.deletion.entity_tables' => [
                'BBVA' => [
                    'cartera_contactos',
                    'cartera_direcciones',
                    'cartera_operaciones',
                    'raw_cartera_bbva',
                ],
                'CAJA_AREQUIPA' => [
                    'cartera_caja_arequipa_detalle',
                    'cartera_avales',
                    'cartera_garantias',
                    'cartera_contactos',
                    'cartera_direcciones',
                    'cartera_operaciones',
                    'raw_cartera_caja_arequipa',
                ],
                'COMPARTAMOS' => [
                    'cartera_compartamos_detalle',
                    'cartera_contactos',
                    'cartera_direcciones',
                    'cartera_operaciones',
                    'raw_cartera_compartamos',
                ],
                'CONFIANZA' => [
                    'cartera_confianza_detalle',
                    'cartera_contactos',
                    'cartera_direcciones',
                    'cartera_operaciones',
                    'raw_cartera_confianza',
                ],
                'WANDOO' => [
                    'cartera_wandoo_detalle',
                    'cartera_direcciones',
                    'cartera_operaciones',
                    'raw_cartera_wandoo',
                ],
            ],
        ]);

        $this->createImportSchema();
    }

    protected function tearDown(): void
    {
        Carbon::setTestNow();

        parent::tearDown();
    }

    protected function validCsv(string $name = 'pagos.csv', ?string $contents = null): UploadedFile
    {
        return UploadedFile::fake()->createWithContent(
            $name,
            $contents ?? "FECHA,DOCUMENTO,MONTO,ACUMULADO,RECAUDO,OPERACION,COMENTARIO,HORA\n2026-10-01,3241,200,200,BCP,0060814,Pago,21:05:36\n",
        );
    }

    protected function validXlsx(string $name = 'pagos.xlsx'): UploadedFile
    {
        $path = tempnam(storage_path('framework/testing'), 'kpdm-xlsx-');

        if ($path === false) {
            $this->fail('No se pudo crear el XLSX temporal de prueba.');
        }

        $archive = new ZipArchive;
        $this->assertTrue($archive->open($path, ZipArchive::CREATE | ZipArchive::OVERWRITE));
        $archive->addFromString('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>');
        $archive->addFromString('xl/workbook.xml', '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"></workbook>');
        $archive->close();

        return new UploadedFile(
            path: $path,
            originalName: $name,
            mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            error: null,
            test: true,
        );
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    protected function createBatch(array $overrides = []): int
    {
        return (int) DB::connection('sqlite')->table('import_batch')->insertGetId(array_merge([
            'tipo' => ImportType::Payments->value,
            'origen' => ImportOrigin::Daily->value,
            'archivo' => 'pagos.csv',
            'archivo_original' => 'pagos.csv',
            'archivo_interno' => 'internal.csv',
            'archivo_ruta' => '2026/10/1/internal.csv',
            'archivo_extension' => 'csv',
            'archivo_mime' => 'text/plain',
            'archivo_tamano' => 128,
            'archivo_sha256' => hash('sha256', uniqid('', true)),
            'fecha_inicio' => '2026-10-05 03:30:00',
            'fecha_fin' => null,
            'estado' => ImportStatus::Pending->value,
            'filas_archivo' => 0,
            'filas_insertadas' => 0,
            'filas_duplicadas' => 0,
            'filas_error' => 0,
            'usuario' => 'user:1',
            'mensaje_error' => null,
        ], $overrides), 'batch_id');
    }

    protected function batchRow(int $batchId): object
    {
        return DB::connection('sqlite')->table('import_batch')->where('batch_id', $batchId)->firstOrFail();
    }

    private function createImportSchema(): void
    {
        foreach ([
            'import_scope_document',
            'import_column_mapping',
            'import_dataset_source',
            'import_source',
            'import_dataset',
            'search_raw_row',
            'import_deletion_log',
            'raw_cartera_confianza',
            'raw_cartera_wandoo',
            'raw_cartera_compartamos',
            'raw_cartera_caja_arequipa',
            'raw_cartera_bbva',
            'cartera_compartamos_detalle',
            'cartera_confianza_detalle',
            'cartera_wandoo_detalle',
            'cartera_garantias',
            'cartera_avales',
            'cartera_caja_arequipa_detalle',
            'cartera_direcciones',
            'cartera_contactos',
            'cartera_operaciones',
        ] as $table) {
            Schema::connection('sqlite')->dropIfExists($table);
        }
        Schema::connection('sqlite')->dropIfExists('import_error');
        Schema::connection('sqlite')->dropIfExists('import_batch');
        Schema::connection('sqlite')->dropIfExists('raw_pagos_import_guard');

        Schema::connection('sqlite')->create('import_batch', function (Blueprint $table): void {
            $table->id('batch_id');
            $table->string('tipo', 50);
            $table->string('entidad', 50)->nullable();
            $table->string('perfil_version', 20)->nullable();
            $table->string('dataset_code', 50)->nullable();
            $table->string('source_code', 64)->nullable();
            $table->string('refresh_mode', 20)->nullable();
            $table->string('origen', 50)->nullable();
            $table->string('archivo');
            $table->string('archivo_original')->nullable();
            $table->string('archivo_interno')->nullable();
            $table->string('archivo_ruta', 500)->nullable();
            $table->string('archivo_extension', 20)->nullable();
            $table->string('archivo_mime', 150)->nullable();
            $table->unsignedBigInteger('archivo_tamano')->nullable();
            $table->string('archivo_sha256', 64)->nullable()->index();
            $table->dateTime('fecha_inicio');
            $table->dateTime('fecha_fin')->nullable();
            $table->string('estado', 30);
            $table->unsignedBigInteger('filas_archivo')->default(0);
            $table->unsignedBigInteger('filas_insertadas')->default(0);
            $table->unsignedBigInteger('filas_duplicadas')->default(0);
            $table->unsignedBigInteger('filas_error')->default(0);
            $table->unsignedBigInteger('rows_valid')->nullable();
            $table->unsignedBigInteger('rows_invalid')->nullable();
            $table->unsignedBigInteger('rows_published')->nullable();
            $table->unsignedBigInteger('scope_count')->nullable();
            $table->dateTime('received_at')->nullable();
            $table->dateTime('validated_at')->nullable();
            $table->dateTime('published_at')->nullable();
            $table->unsignedBigInteger('uploaded_by_user_id')->nullable();
            $table->unsignedInteger('mapping_version')->nullable();
            $table->string('idempotency_key', 64)->nullable()->unique();
            $table->string('usuario', 100)->nullable();
            $table->text('mensaje_error')->nullable();
        });

        Schema::connection('sqlite')->create('import_error', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('batch_id');
            $table->unsignedBigInteger('numero_fila');
            $table->string('campo', 100)->nullable();
            $table->text('valor')->nullable();
            $table->string('error', 500);
            $table->dateTime('created_at');
            $table->index(['batch_id', 'numero_fila']);
        });

        Schema::connection('sqlite')->create('import_deletion_log', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('batch_id_original');
            $table->string('tipo', 50);
            $table->string('entidad', 50)->nullable();
            $table->string('origen', 50)->nullable();
            $table->string('archivo_original')->nullable();
            $table->string('archivo_interno')->nullable();
            $table->string('file_hash', 64)->nullable();
            $table->unsignedBigInteger('filas_archivo')->default(0);
            $table->unsignedBigInteger('filas_insertadas')->default(0);
            $table->unsignedBigInteger('filas_error')->default(0);
            $table->unsignedBigInteger('deleted_by_user_id');
            $table->string('deleted_by_name', 255);
            $table->dateTime('deleted_at');
            $table->boolean('file_deleted')->default(false);
            $table->string('warning', 500)->nullable();
        });

        Schema::connection('sqlite')->create('import_dataset', function (Blueprint $table): void {
            $table->string('dataset_code', 50)->primary();
            $table->string('label', 100);
            $table->string('description', 500)->nullable();
            $table->unsignedSmallInteger('sort_order')->default(0);
            $table->boolean('is_active')->default(true);
            $table->dateTime('created_at');
            $table->dateTime('updated_at');
        });

        Schema::connection('sqlite')->create('import_source', function (Blueprint $table): void {
            $table->string('source_code', 64)->primary();
            $table->string('label', 150);
            $table->string('description', 500)->nullable();
            $table->boolean('is_active')->default(true);
            $table->dateTime('created_at');
            $table->dateTime('updated_at');
        });

        Schema::connection('sqlite')->create('import_dataset_source', function (Blueprint $table): void {
            $table->string('dataset_code', 50);
            $table->string('source_code', 64);
            $table->string('default_refresh_mode', 20);
            $table->boolean('allows_full_replace')->default(false);
            $table->boolean('allows_scope_replace')->default(false);
            $table->boolean('allows_upsert')->default(false);
            $table->unsignedInteger('current_mapping_version')->nullable();
            $table->boolean('is_active')->default(true);
            $table->dateTime('created_at');
            $table->dateTime('updated_at');
            $table->primary(['dataset_code', 'source_code']);
        });

        Schema::connection('sqlite')->create('import_column_mapping', function (Blueprint $table): void {
            $table->id('mapping_id');
            $table->string('dataset_code', 50);
            $table->string('source_code', 64);
            $table->unsignedInteger('mapping_version');
            $table->unsignedSmallInteger('source_position');
            $table->string('source_column');
            $table->string('target_column', 100);
            $table->boolean('is_required')->default(false);
            $table->string('transformation', 100)->nullable();
            $table->text('default_value')->nullable();
            $table->boolean('is_active')->default(true);
            $table->dateTime('created_at');
            $table->dateTime('updated_at');
            $table->unique(['dataset_code', 'source_code', 'mapping_version', 'source_position']);
            $table->unique(['dataset_code', 'source_code', 'mapping_version', 'target_column']);
        });

        Schema::connection('sqlite')->create('import_scope_document', function (Blueprint $table): void {
            $table->id();
            $table->unsignedBigInteger('batch_id');
            $table->string('documento', 100);
            $table->dateTime('created_at');
            $table->unique(['batch_id', 'documento']);
        });

        Schema::connection('sqlite')->create('search_raw_row', function (Blueprint $table): void {
            $table->id('raw_id');
            $table->unsignedBigInteger('batch_id');
            $table->string('dataset_code', 50);
            $table->string('source_code', 64);
            $table->unsignedBigInteger('source_row');
            $table->string('source_file');
            $table->json('raw_payload');
            $table->string('row_hash', 64);
            $table->dateTime('ingested_at');
        });

        foreach ([
            'cartera_operaciones',
            'cartera_contactos',
            'cartera_direcciones',
            'cartera_caja_arequipa_detalle',
            'cartera_avales',
            'cartera_garantias',
            'cartera_compartamos_detalle',
            'cartera_confianza_detalle',
            'cartera_wandoo_detalle',
            'raw_cartera_bbva',
            'raw_cartera_caja_arequipa',
            'raw_cartera_compartamos',
            'raw_cartera_confianza',
            'raw_cartera_wandoo',
        ] as $tableName) {
            Schema::connection('sqlite')->create($tableName, function (Blueprint $table): void {
                $table->id();
                $table->unsignedBigInteger('batch_id')->index();
                $table->string('payload')->nullable();
            });
        }

        Schema::connection('sqlite')->create('raw_pagos_import_guard', function (Blueprint $table): void {
            $table->id('raw_id');
            $table->string('DOCUMENTO', 30)->nullable();
        });
    }
}
