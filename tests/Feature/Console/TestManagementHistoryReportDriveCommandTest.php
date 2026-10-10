<?php

namespace Tests\Feature\Console;

use App\Services\Reports\ManagementHistoryDriveDiagnostic;
use App\Services\Reports\ManagementHistoryDriveDiagnosticResult;
use Closure;
use Mockery;
use RuntimeException;
use Tests\TestCase;

class TestManagementHistoryReportDriveCommandTest extends TestCase
{
    public function test_command_reports_successful_read_only_diagnostic(): void
    {
        $diagnostic = Mockery::mock(ManagementHistoryDriveDiagnostic::class);
        $diagnostic->shouldReceive('run')
            ->once()
            ->with(Mockery::type(Closure::class))
            ->andReturnUsing(function (Closure $progress): ManagementHistoryDriveDiagnosticResult {
                $progress('[1/4] Validando configuración...');
                $progress('[2/4] Autenticando con Google Drive...');
                $progress('[3/4] Verificando Unidad compartida...');
                $progress('[4/4] Verificando carpeta destino...');

                return new ManagementHistoryDriveDiagnosticResult(true);
            });
        $this->app->instance(ManagementHistoryDriveDiagnostic::class, $diagnostic);

        $this->artisan('reports:gestiones-drive-test')
            ->expectsOutputToContain('[1/4] Validando configuración...')
            ->expectsOutputToContain('[2/4] Autenticando con Google Drive...')
            ->expectsOutputToContain('[3/4] Verificando Unidad compartida...')
            ->expectsOutputToContain('[4/4] Verificando carpeta destino...')
            ->expectsOutputToContain('Google Drive configurado correctamente.')
            ->expectsOutputToContain('Unidad compartida: accesible')
            ->expectsOutputToContain('Carpeta destino: accesible')
            ->assertSuccessful();
    }

    public function test_command_reports_safe_failure_without_exposing_secrets(): void
    {
        $diagnostic = Mockery::mock(ManagementHistoryDriveDiagnostic::class);
        $diagnostic->shouldReceive('run')
            ->once()
            ->andThrow(new RuntimeException('private_key=secret access_token=secret-token'));
        $this->app->instance(ManagementHistoryDriveDiagnostic::class, $diagnostic);

        $this->artisan('reports:gestiones-drive-test')
            ->expectsOutputToContain('No fue posible validar Google Drive. Revisa el log para obtener más información.')
            ->doesntExpectOutputToContain('private_key')
            ->doesntExpectOutputToContain('secret-token')
            ->assertFailed();
    }
}
