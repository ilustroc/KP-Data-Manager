<?php

namespace Tests\Feature\Imports;

use App\ImportStatus;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;

class RegisterImportCommandTest extends ImportFeatureTestCase
{
    public function test_cli_registers_and_moves_file_from_configured_inbox(): void
    {
        Storage::fake('imports');
        Storage::fake('inbox');
        config(['imports.inbox_path' => Storage::disk('inbox')->path('')]);
        Storage::disk('inbox')->put('pagos_2024.csv', 'historical contents');

        $this->artisan('kpdm:import:register', [
            '--file' => 'pagos_2024.csv',
            '--tipo' => 'PAGOS',
            '--origen' => 'HISTORICO',
        ])
            ->expectsOutputToContain('registrado en estado PENDIENTE')
            ->assertSuccessful();

        $batch = DB::connection('sqlite')->table('import_batch')->firstOrFail();
        $this->assertSame(ImportStatus::Pending->value, $batch->estado);
        $this->assertStringStartsWith('cli:', $batch->usuario);
        Storage::disk('imports')->assertExists($batch->archivo_ruta);
        Storage::disk('inbox')->assertMissing('pagos_2024.csv');
    }

    public function test_cli_rejects_path_traversal(): void
    {
        Storage::fake('imports');
        Storage::fake('inbox');
        config(['imports.inbox_path' => Storage::disk('inbox')->path('')]);

        $this->artisan('kpdm:import:register', [
            '--file' => '../secret.csv',
        ])
            ->expectsOutputToContain('intenta salir del inbox')
            ->assertFailed();

        $this->assertDatabaseCount('import_batch', 0);
    }

    public function test_cli_rejects_absolute_path_outside_inbox(): void
    {
        Storage::fake('imports');
        Storage::fake('inbox');
        config(['imports.inbox_path' => Storage::disk('inbox')->path('')]);

        $this->artisan('kpdm:import:register', [
            '--file' => storage_path('outside.csv'),
        ])
            ->expectsOutputToContain('Solo se aceptan rutas relativas')
            ->assertFailed();

        $this->assertDatabaseCount('import_batch', 0);
    }
}
