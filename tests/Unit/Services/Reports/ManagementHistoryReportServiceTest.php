<?php

namespace Tests\Unit\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use App\Mail\ManagementHistoryReportMail;
use App\Services\Reports\ManagementHistoryExport;
use App\Services\Reports\ManagementHistoryReportExporter;
use App\Services\Reports\ManagementHistoryReportPhone;
use App\Services\Reports\ManagementHistoryReportQuery;
use App\Services\Reports\ManagementHistoryReportRecipients;
use App\Services\Reports\ManagementHistoryReportService;
use App\Services\Reports\ManagementHistoryReportStorage;
use App\Services\Reports\ManagementHistoryReportTransformer;
use App\Services\Reports\StoredManagementHistoryReport;
use Carbon\CarbonImmutable;
use Illuminate\Mail\PendingMail;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\LazyCollection;
use Mockery;
use RuntimeException;
use Symfony\Component\Mailer\Exception\UnexpectedResponseException;
use Tests\TestCase;

class ManagementHistoryReportServiceTest extends TestCase
{
    public function test_uploads_single_export_sends_drive_link_without_attachment_and_removes_temporary_file(): void
    {
        Mail::fake();
        Log::spy();
        $temporaryRoot = $this->configureReport();
        $query = Mockery::mock(ManagementHistoryReportQuery::class);
        $query->shouldReceive('cursor')
            ->once()
            ->andReturn(LazyCollection::make(fn () => yield $this->sourceRow()));
        $storage = Mockery::mock(ManagementHistoryReportStorage::class);
        $storage->shouldReceive('store')
            ->once()
            ->with(Mockery::on(fn (ManagementHistoryExport $export): bool => is_file($export->path)
                && $export->filename === 'historico_gestiones_20261008.xlsx'
                && $export->recordCount === 1))
            ->andReturn($this->storedReport());
        $service = $this->service($query, $storage);
        $progress = [];

        $result = $service->send(
            CarbonImmutable::parse('2026-10-09 10:00:00', 'America/Lima'),
            function (string $message) use (&$progress): void {
                $progress[] = $message;
            },
        );

        $this->assertSame(1, $result->recordCount);
        $this->assertSame(2, $result->recipientCount);
        $this->assertSame('historico_gestiones.xlsx', $result->filename);
        $this->assertSame([
            '[1/5] Calculando periodo...',
            '[2/5] Generando reporte XLSX...',
            'Reporte generado: 1 registros.',
            '[3/5] Subiendo reporte a Google Drive...',
            'Reporte almacenado correctamente en Drive.',
            '[4/5] Enviando correo...',
            '[5/5] Limpiando archivo temporal...',
        ], $progress);
        $this->assertSame([], glob($temporaryRoot.DIRECTORY_SEPARATOR.'*') ?: []);
        Mail::assertSent(ManagementHistoryReportMail::class, function (ManagementHistoryReportMail $mail): bool {
            return $mail->hasTo('reportes@kpinvest.pe')
                && $mail->hasTo('operaciones@kpinvest.pe')
                && $mail->filename === 'historico_gestiones.xlsx'
                && $mail->downloadUrl === 'https://drive.google.com/file/d/private-file-id/view';
        });
        Log::shouldHaveReceived('info')
            ->with(
                'drive_upload_completed',
                Mockery::on(function (array $context): bool {
                    $serializedContext = json_encode($context);

                    return $context['remote_filename'] === 'historico_gestiones.xlsx'
                        && $context['size_bytes'] === 12345
                        && $context['record_count'] === 1
                        && $context['period'] === '01/10/2025 - 08/10/2026'
                        && is_float($context['drive_upload_duration_seconds'])
                        && is_string($serializedContext)
                        && ! str_contains($serializedContext, 'private-file-id')
                        && ! str_contains($serializedContext, 'drive.google.com');
                }),
            )
            ->once();
        @rmdir($temporaryRoot);
    }

    public function test_removes_temporary_file_when_email_delivery_fails(): void
    {
        $temporaryRoot = $this->configureReport();
        $query = Mockery::mock(ManagementHistoryReportQuery::class);
        $query->shouldReceive('cursor')
            ->once()
            ->andReturn(LazyCollection::make(fn () => yield $this->sourceRow()));
        $storage = Mockery::mock(ManagementHistoryReportStorage::class);
        $storage->shouldReceive('store')->once()->andReturn($this->storedReport());
        Mail::shouldReceive('to')
            ->once()
            ->andThrow(new RuntimeException('Fallo SMTP simulado'));

        try {
            $this->service($query, $storage)->send(
                CarbonImmutable::parse('2026-10-09 10:00:00', 'America/Lima'),
            );
            $this->fail('Se esperaba una excepción de envío.');
        } catch (RuntimeException $exception) {
            $this->assertSame('Fallo SMTP simulado', $exception->getMessage());
            $this->assertSame([], glob($temporaryRoot.DIRECTORY_SEPARATOR.'*') ?: []);
        } finally {
            @rmdir($temporaryRoot);
        }
    }

    public function test_logs_sanitized_smtp_diagnostic_and_removes_temporary_file_when_server_rejects_email(): void
    {
        Log::spy();
        $temporaryRoot = $this->configureReport();
        $query = Mockery::mock(ManagementHistoryReportQuery::class);
        $query->shouldReceive('cursor')
            ->once()
            ->andReturn(LazyCollection::make(fn () => yield $this->sourceRow()));
        $storage = Mockery::mock(ManagementHistoryReportStorage::class);
        $storage->shouldReceive('store')->once()->andReturn($this->storedReport());
        $pendingMail = Mockery::mock(PendingMail::class);
        $pendingMail->shouldReceive('send')
            ->once()
            ->andThrow(new UnexpectedResponseException(
                'Expected response code "250" but got code "552", with message "552 5.3.4 Message size exceeds fixed maximum message size password=smtp-secret smtp://mailer:dsn-secret@smtp.example.com recipient@example.com".',
                552,
            ));
        Mail::shouldReceive('to')
            ->once()
            ->with(['reportes@kpinvest.pe', 'operaciones@kpinvest.pe'])
            ->andReturn($pendingMail);

        try {
            $this->service($query, $storage)->send(
                CarbonImmutable::parse('2026-10-09 10:00:00', 'America/Lima'),
            );
            $this->fail('Se esperaba un rechazo del servidor SMTP.');
        } catch (UnexpectedResponseException $exception) {
            $this->assertSame(552, $exception->getCode());
            $this->assertSame([], glob($temporaryRoot.DIRECTORY_SEPARATOR.'*') ?: []);
            Log::shouldHaveReceived('error')
                ->once()
                ->withArgs(function (string $message, array $context): bool {
                    $serializedContext = json_encode($context);

                    return $message === 'El servidor SMTP rechazó el reporte histórico de gestiones.'
                        && $context['exception_class'] === UnexpectedResponseException::class
                        && $context['smtp_response_code'] === 552
                        && str_contains($context['smtp_response'], 'Message size exceeds fixed maximum message size')
                        && is_int($context['report_size_bytes'])
                        && $context['report_size_bytes'] > 0
                        && is_string($serializedContext)
                        && ! str_contains($serializedContext, 'smtp-secret')
                        && ! str_contains($serializedContext, 'dsn-secret')
                        && ! str_contains($serializedContext, 'recipient@example.com');
                });
        } finally {
            @rmdir($temporaryRoot);
        }
    }

    public function test_drive_failure_prevents_email_and_removes_temporary_file_without_logging_secrets(): void
    {
        Mail::fake();
        Log::spy();
        $temporaryRoot = $this->configureReport();
        $query = Mockery::mock(ManagementHistoryReportQuery::class);
        $query->shouldReceive('cursor')
            ->once()
            ->andReturn(LazyCollection::make(fn () => yield $this->sourceRow()));
        $storage = Mockery::mock(ManagementHistoryReportStorage::class);
        $storage->shouldReceive('store')
            ->once()
            ->andThrow(new ManagementHistoryReportStorageException(
                'Google Drive no pudo almacenar el reporte.',
                previous: new RuntimeException('access_token=token-super-secret private_key=key-super-secret'),
            ));

        try {
            $this->service($query, $storage)->send(
                CarbonImmutable::parse('2026-10-09 10:00:00', 'America/Lima'),
            );
            $this->fail('Se esperaba un fallo controlado de Google Drive.');
        } catch (ManagementHistoryReportStorageException) {
            $this->assertSame([], glob($temporaryRoot.DIRECTORY_SEPARATOR.'*') ?: []);
            Mail::assertNothingSent();
            Log::shouldHaveReceived('error')
                ->once()
                ->withArgs(function (string $message, array $context): bool {
                    $serializedContext = json_encode($context);

                    return $message === 'drive_upload_failed'
                        && is_string($serializedContext)
                        && ! str_contains($serializedContext, 'token-super-secret')
                        && ! str_contains($serializedContext, 'key-super-secret');
                });
        } finally {
            @rmdir($temporaryRoot);
        }
    }

    private function configureReport(): string
    {
        $temporaryRoot = sys_get_temp_dir().DIRECTORY_SEPARATOR.'kpdm-report-service-'.bin2hex(random_bytes(8));
        config([
            'reports.management_history.recipients' => 'reportes@kpinvest.pe,operaciones@kpinvest.pe',
            'reports.management_history.temporary_directory' => $temporaryRoot,
            'reports.management_history.filename_prefix' => 'historico_gestiones',
            'reports.management_history.timezone' => 'America/Lima',
            'reports.management_history.source_timezone' => 'UTC',
            'reports.management_history.drive.filename' => 'historico_gestiones.xlsx',
        ]);

        return $temporaryRoot;
    }

    private function service(
        ManagementHistoryReportQuery $query,
        ManagementHistoryReportStorage $storage,
    ): ManagementHistoryReportService {
        return new ManagementHistoryReportService(
            query: $query,
            transformer: new ManagementHistoryReportTransformer(new ManagementHistoryReportPhone),
            exporter: new ManagementHistoryReportExporter,
            recipients: new ManagementHistoryReportRecipients,
            storage: $storage,
        );
    }

    private function storedReport(): StoredManagementHistoryReport
    {
        return new StoredManagementHistoryReport(
            fileId: 'private-file-id',
            filename: 'historico_gestiones.xlsx',
            webViewLink: 'https://drive.google.com/file/d/private-file-id/view',
            sizeBytes: 12345,
        );
    }

    private function sourceRow(): object
    {
        return (object) [
            'created_at' => '2026-10-02 15:28:00',
            'nombre_cliente' => 'Cliente de prueba',
            'documento' => '00001234',
            'telefono' => '+51934043966',
            'agente_nombre' => 'Agente Uno',
            'canal' => 'LLAMADA',
            'tipificacion_n1' => 'CONTACTO',
            'tipificacion_n2' => 'YA_PAGO',
            'tipificacion_n3' => 'VALIDADO',
            'resultado' => 'GESTIONADO',
            'duracion' => 45,
            'promesa' => 'Si',
            'monto' => '150.75',
            'comentario' => 'Nota sintética',
        ];
    }
}
