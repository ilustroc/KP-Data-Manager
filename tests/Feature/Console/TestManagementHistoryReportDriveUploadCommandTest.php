<?php

namespace Tests\Feature\Console;

use App\Services\Reports\ManagementHistoryDriveUploadDiagnostic;
use App\Services\Reports\ManagementHistoryDriveUploadDiagnosticResult;
use App\Services\Reports\ManagementHistoryReportQuery;
use App\Services\Reports\ManagementHistoryReportService;
use Closure;
use Illuminate\Support\Facades\Mail;
use Mockery;
use RuntimeException;
use Tests\TestCase;

class TestManagementHistoryReportDriveUploadCommandTest extends TestCase
{
    public function test_command_reports_successful_write_read_and_trash_diagnostic(): void
    {
        Mail::fake();
        $query = Mockery::mock(ManagementHistoryReportQuery::class);
        $query->shouldNotReceive('cursor');
        $this->app->instance(ManagementHistoryReportQuery::class, $query);
        $reportService = Mockery::mock(ManagementHistoryReportService::class);
        $reportService->shouldNotReceive('send');
        $this->app->instance(ManagementHistoryReportService::class, $reportService);
        $diagnostic = Mockery::mock(ManagementHistoryDriveUploadDiagnostic::class);
        $diagnostic->shouldReceive('run')
            ->once()
            ->with(Mockery::type(Closure::class))
            ->andReturnUsing(function (Closure $progress): ManagementHistoryDriveUploadDiagnosticResult {
                $progress('[1/5] Validando configuración...');
                $progress('[2/5] Creando archivo temporal...');
                $progress('[3/5] Probando escritura en Google Drive...');
                $progress('[4/5] Verificando archivo remoto...');
                $progress('[5/5] Moviendo archivo de prueba a la papelera...');

                return new ManagementHistoryDriveUploadDiagnosticResult(true, true, true, true, false);
            });
        $this->app->instance(ManagementHistoryDriveUploadDiagnostic::class, $diagnostic);

        $this->artisan('reports:gestiones-drive-upload-test')
            ->expectsOutputToContain('[1/5] Validando configuración...')
            ->expectsOutputToContain('[2/5] Creando archivo temporal...')
            ->expectsOutputToContain('[3/5] Probando escritura en Google Drive...')
            ->expectsOutputToContain('[4/5] Verificando archivo remoto...')
            ->expectsOutputToContain('[5/5] Moviendo archivo de prueba a la papelera...')
            ->expectsOutputToContain('Escritura en Google Drive validada correctamente.')
            ->expectsOutputToContain('Creación: OK')
            ->expectsOutputToContain('Lectura: OK')
            ->expectsOutputToContain('Papelera: OK')
            ->expectsOutputToContain('Capabilities: canTrash=true · canDelete=false')
            ->assertSuccessful();

        Mail::assertNothingSent();
    }

    public function test_command_reports_safe_failure_without_exposing_google_secrets(): void
    {
        Mail::fake();
        $diagnostic = Mockery::mock(ManagementHistoryDriveUploadDiagnostic::class);
        $diagnostic->shouldReceive('run')
            ->once()
            ->andThrow(new RuntimeException('private_key=secret access_token=secret-token'));
        $this->app->instance(ManagementHistoryDriveUploadDiagnostic::class, $diagnostic);

        $this->artisan('reports:gestiones-drive-upload-test')
            ->expectsOutputToContain('No fue posible escribir en Google Drive.')
            ->expectsOutputToContain('Revisa el log para conocer el código y motivo de Google API.')
            ->doesntExpectOutputToContain('private_key')
            ->doesntExpectOutputToContain('secret-token')
            ->assertFailed();

        Mail::assertNothingSent();
    }
}
