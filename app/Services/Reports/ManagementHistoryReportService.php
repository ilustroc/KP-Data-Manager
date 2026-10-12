<?php

namespace App\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use App\Mail\ManagementHistoryReportMail;
use Carbon\CarbonImmutable;
use Closure;
use DateTimeInterface;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;
use Illuminate\Support\Str;
use Symfony\Component\Mailer\Exception\UnexpectedResponseException;

class ManagementHistoryReportService
{
    public function __construct(
        private readonly ManagementHistoryReportQuery $query,
        private readonly ManagementHistoryReportTransformer $transformer,
        private readonly ManagementHistoryReportExporter $exporter,
        private readonly ManagementHistoryReportRecipients $recipients,
        private readonly ManagementHistoryReportStorage $storage,
    ) {}

    public function send(
        ?DateTimeInterface $executedAt = null,
        ?Closure $progress = null,
    ): ManagementHistoryReportResult {
        $totalStartedAt = hrtime(true);
        $progress?->__invoke('[1/5] Calculando periodo...');
        $executedAt ??= CarbonImmutable::now(
            (string) config('reports.management_history.timezone', 'America/Lima'),
        );
        $period = ManagementHistoryReportPeriod::forExecution($executedAt);
        $configuredRecipients = $this->recipients->configured();

        $progress?->__invoke('[2/5] Generando reporte XLSX...');
        $exportStartedAt = hrtime(true);
        $export = $this->exporter->export($this->transformedRows($period), $period);
        $exportDurationSeconds = $this->elapsedSeconds($exportStartedAt);
        $reportSizeBytes = $this->attachmentSizeBytes($export->path);
        $progress?->__invoke("Reporte generado: {$export->recordCount} registros.");

        Log::info('management_history_export_completed', [
            'local_filename' => $export->filename,
            'size_bytes' => $reportSizeBytes,
            'size_mb' => $reportSizeBytes === null ? null : round($reportSizeBytes / 1024 / 1024, 2),
            'record_count' => $export->recordCount,
            'period' => "{$period->displayStart()} - {$period->displayEnd()}",
            'export_duration_seconds' => $exportDurationSeconds,
            'records_per_second' => $exportDurationSeconds > 0
                ? round($export->recordCount / $exportDurationSeconds, 2)
                : null,
        ]);

        $driveUploadDurationSeconds = null;
        $mailDurationSeconds = null;

        try {
            $progress?->__invoke('[3/5] Subiendo reporte a Google Drive...');
            $driveUploadStartedAt = hrtime(true);
            Log::info('drive_upload_started', [
                'remote_filename' => (string) config(
                    'reports.management_history.drive.filename',
                    'historico_gestiones.xlsx',
                ),
                'size_bytes' => $reportSizeBytes,
                'record_count' => $export->recordCount,
                'period' => "{$period->displayStart()} - {$period->displayEnd()}",
            ]);

            try {
                $storedReport = $this->storage->store($export);
            } catch (ManagementHistoryReportStorageException $exception) {
                Log::error('drive_upload_failed', [
                    'exception_class' => $exception::class,
                    'remote_filename' => (string) config(
                        'reports.management_history.drive.filename',
                        'historico_gestiones.xlsx',
                    ),
                    'size_bytes' => $reportSizeBytes,
                    'record_count' => $export->recordCount,
                    'period' => "{$period->displayStart()} - {$period->displayEnd()}",
                    'drive_upload_duration_seconds' => $this->elapsedSeconds($driveUploadStartedAt),
                ]);

                throw $exception;
            }

            $driveUploadDurationSeconds = $this->elapsedSeconds($driveUploadStartedAt);
            Log::info('drive_upload_completed', [
                'remote_filename' => $storedReport->filename,
                'size_bytes' => $storedReport->sizeBytes,
                'record_count' => $export->recordCount,
                'period' => "{$period->displayStart()} - {$period->displayEnd()}",
                'drive_upload_duration_seconds' => $driveUploadDurationSeconds,
                'file_id_hash' => substr(hash('sha256', $storedReport->fileId), 0, 12),
            ]);
            $progress?->__invoke('Reporte almacenado correctamente en Drive.');

            $progress?->__invoke('[4/5] Enviando correo...');
            $mailStartedAt = hrtime(true);
            Log::info('management_history_mail_started', [
                'remote_filename' => $storedReport->filename,
                'size_bytes' => $storedReport->sizeBytes,
                'size_mb' => round($storedReport->sizeBytes / 1024 / 1024, 2),
                'record_count' => $export->recordCount,
                'recipient_count' => count($configuredRecipients),
                'period' => "{$period->displayStart()} - {$period->displayEnd()}",
            ]);

            Mail::to($configuredRecipients)->send(new ManagementHistoryReportMail(
                generatedAt: $period->generatedAtLocal->toDateTimeImmutable(),
                periodFrom: $period->startLocal->toDateTimeImmutable(),
                periodTo: $period->cutoffDateLocal()->toDateTimeImmutable(),
                recordCount: $export->recordCount,
                filename: $storedReport->filename,
                downloadUrl: $storedReport->webViewLink,
            ));
            $mailDurationSeconds = $this->elapsedSeconds($mailStartedAt);

            Log::info('management_history_mail_completed', [
                'remote_filename' => $storedReport->filename,
                'record_count' => $export->recordCount,
                'recipient_count' => count($configuredRecipients),
                'period' => "{$period->displayStart()} - {$period->displayEnd()}",
                'mail_duration_seconds' => $mailDurationSeconds,
            ]);

            return new ManagementHistoryReportResult(
                period: $period,
                filename: $storedReport->filename,
                recordCount: $export->recordCount,
                recipientCount: count($configuredRecipients),
            );
        } catch (UnexpectedResponseException $exception) {
            $mailDurationSeconds = isset($mailStartedAt)
                ? $this->elapsedSeconds($mailStartedAt)
                : null;
            Log::error('El servidor SMTP rechazó el reporte histórico de gestiones.', [
                'exception_class' => $exception::class,
                'smtp_response_code' => $exception->getCode() > 0 ? $exception->getCode() : null,
                'smtp_response' => $this->sanitizeSmtpResponse($exception->getMessage()),
                'report_size_bytes' => $reportSizeBytes,
            ]);

            throw $exception;
        } finally {
            $progress?->__invoke('[5/5] Limpiando archivo temporal...');
            $this->exporter->delete($export);

            Log::info('management_history_report_metrics', [
                'record_count' => $export->recordCount,
                'export_duration_seconds' => $exportDurationSeconds,
                'drive_upload_duration_seconds' => $driveUploadDurationSeconds,
                'mail_duration_seconds' => $mailDurationSeconds,
                'total_duration_seconds' => $this->elapsedSeconds($totalStartedAt),
                'records_per_second' => $exportDurationSeconds > 0
                    ? round($export->recordCount / $exportDurationSeconds, 2)
                    : null,
            ]);
        }
    }

    /**
     * @return iterable<array<string, mixed>>
     */
    private function transformedRows(ManagementHistoryReportPeriod $period): iterable
    {
        foreach ($this->query->cursor($period) as $source) {
            $row = $this->transformer->transform($source);

            if ($row !== null) {
                yield $row;
            }
        }
    }

    private function attachmentSizeBytes(string $path): ?int
    {
        $size = @filesize($path);

        return $size === false ? null : $size;
    }

    private function elapsedSeconds(int $startedAt): float
    {
        return round((hrtime(true) - $startedAt) / 1_000_000_000, 3);
    }

    private function sanitizeSmtpResponse(string $response): string
    {
        $sanitized = preg_replace('/[\r\n\t]+/', ' ', $response) ?? '';
        $sanitized = preg_replace(
            '/\b(smtps?):\/\/[^@\s]+@/i',
            '$1://[credentials-redacted]@',
            $sanitized,
        ) ?? '';
        $sanitized = preg_replace(
            '/\b(password|passwd|pass|token|secret|authorization)\s*[:=]\s*(?:"[^"]*"|\'[^\']*\'|[^\s,;]+)/i',
            '$1=[redacted]',
            $sanitized,
        ) ?? '';
        $sanitized = preg_replace('/\bBearer\s+[^\s,;]+/i', 'Bearer [redacted]', $sanitized) ?? '';
        $sanitized = preg_replace(
            '/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}/i',
            '[email-redacted]',
            $sanitized,
        ) ?? '';

        return Str::limit(trim($sanitized), 1000, '…');
    }
}
