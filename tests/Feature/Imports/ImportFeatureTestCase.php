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
            'imports.max_web_upload_mb' => 50,
            'imports.allowed_extensions' => ['csv', 'xlsx'],
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
        Schema::connection('sqlite')->dropIfExists('import_error');
        Schema::connection('sqlite')->dropIfExists('import_batch');
        Schema::connection('sqlite')->dropIfExists('raw_pagos_import_guard');

        Schema::connection('sqlite')->create('import_batch', function (Blueprint $table): void {
            $table->id('batch_id');
            $table->string('tipo', 50);
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

        Schema::connection('sqlite')->create('raw_pagos_import_guard', function (Blueprint $table): void {
            $table->id('raw_id');
            $table->string('DOCUMENTO', 30)->nullable();
        });
    }
}
