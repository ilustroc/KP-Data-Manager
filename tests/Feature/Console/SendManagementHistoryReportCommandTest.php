<?php

namespace Tests\Feature\Console;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use App\Services\Reports\ManagementHistoryReportPeriod;
use App\Services\Reports\ManagementHistoryReportQuery;
use App\Services\Reports\ManagementHistoryReportResult;
use App\Services\Reports\ManagementHistoryReportService;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\Mail;
use Mockery;
use Symfony\Component\Mailer\Exception\UnexpectedResponseException;
use Tests\TestCase;

class SendManagementHistoryReportCommandTest extends TestCase
{
    public function test_command_reports_manual_send_result_without_sensitive_data(): void
    {
        $period = ManagementHistoryReportPeriod::forExecution(
            CarbonImmutable::parse('2026-10-09 10:00:00', 'America/Lima'),
        );
        $service = Mockery::mock(ManagementHistoryReportService::class);
        $service->shouldReceive('send')
            ->once()
            ->andReturn(new ManagementHistoryReportResult(
                period: $period,
                filename: 'historico_gestiones.xlsx',
                recordCount: 123456,
                recipientCount: 1,
            ));
        $this->app->instance(ManagementHistoryReportService::class, $service);

        $this->artisan('reports:gestiones-send')
            ->expectsOutputToContain('Reporte histórico enviado correctamente.')
            ->expectsOutputToContain('Periodo: 01/10/2025 - 08/10/2026')
            ->expectsOutputToContain('Registros exportados: 123456')
            ->expectsOutputToContain('Destinatarios: 1')
            ->expectsOutputToContain('Archivo: historico_gestiones.xlsx')
            ->assertSuccessful();
    }

    public function test_command_fails_before_query_when_existing_recipient_resolver_rejects_config(): void
    {
        Mail::fake();
        config(['reports.management_history.recipients' => 'correo-invalido']);
        $query = Mockery::mock(ManagementHistoryReportQuery::class);
        $query->shouldNotReceive('cursor');
        $this->app->instance(ManagementHistoryReportQuery::class, $query);

        $this->artisan('reports:gestiones-send')
            ->expectsOutputToContain('dirección de correo inválida')
            ->assertFailed();

        Mail::assertNothingSent();
    }

    public function test_command_reports_safe_message_when_smtp_server_rejects_email(): void
    {
        $service = Mockery::mock(ManagementHistoryReportService::class);
        $service->shouldReceive('send')
            ->once()
            ->andThrow(new UnexpectedResponseException(
                'Message size exceeds fixed maximum message size password=smtp-secret',
                552,
            ));
        $this->app->instance(ManagementHistoryReportService::class, $service);

        $this->artisan('reports:gestiones-send')
            ->expectsOutputToContain('No fue posible enviar el correo. Revisa el log para conocer la respuesta SMTP.')
            ->doesntExpectOutputToContain('smtp-secret')
            ->assertFailed();
    }

    public function test_command_reports_safe_message_when_drive_storage_fails(): void
    {
        $service = Mockery::mock(ManagementHistoryReportService::class);
        $service->shouldReceive('send')
            ->once()
            ->andThrow(new ManagementHistoryReportStorageException(
                'private_key=key-super-secret access_token=token-super-secret',
            ));
        $this->app->instance(ManagementHistoryReportService::class, $service);

        $this->artisan('reports:gestiones-send')
            ->expectsOutputToContain('No fue posible almacenar el reporte en Google Drive. Revisa el log.')
            ->doesntExpectOutputToContain('key-super-secret')
            ->doesntExpectOutputToContain('token-super-secret')
            ->assertFailed();
    }
}
