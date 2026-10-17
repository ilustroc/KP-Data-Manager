<?php

namespace App\Services\Imports;

use Illuminate\Process\Exceptions\ProcessTimedOutException;
use Illuminate\Process\PendingProcess;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Process;
use JsonException;
use Throwable;

final class EtlProcessRunner
{
    public function run(int $batchId): EtlProcessResult
    {
        return $this->runWorker($batchId, publishOnly: false);
    }

    public function runPublishOnly(int $batchId): EtlProcessResult
    {
        return $this->runWorker($batchId, publishOnly: true);
    }

    private function runWorker(int $batchId, bool $publishOnly): EtlProcessResult
    {
        [$pythonBinary, $workingDirectory] = $this->validatedConfiguration();
        $command = [
            $pythonBinary,
            '-m',
            'src.worker',
            '--batch-id',
            (string) $batchId,
        ];
        if ($publishOnly) {
            $command[] = '--publish-only';
        }
        $startedAt = hrtime(true);

        try {
            $process = Process::path($workingDirectory);
            $process = $this->withConfiguredTimeout($process);
            $result = $process->run($command);
        } catch (ProcessTimedOutException $exception) {
            Log::error('El proceso ETL excedió el tiempo máximo configurado.', [
                'batch_id' => $batchId,
            ]);

            throw new EtlProcessFailed(
                'El procesador ETL excedió el tiempo máximo configurado.',
                previous: $exception,
            );
        } catch (Throwable $exception) {
            Log::error('El sistema operativo no pudo iniciar el proceso ETL.', [
                'batch_id' => $batchId,
                'exception_type' => $exception::class,
            ]);

            throw new EtlProcessStartFailed('No fue posible iniciar el procesador ETL.');
        }

        $stdoutDiagnostic = $this->lastJsonDiagnostic($result->output());
        $stderrDiagnostic = $this->lastJsonDiagnostic($result->errorOutput());
        $diagnostic = $stdoutDiagnostic ?? $stderrDiagnostic ?? [
            'event' => null,
            'stage' => null,
            'error_type' => null,
            'error_code' => null,
            'db_driver' => null,
            'connection_phase' => null,
            'retryable' => null,
        ];
        $etlResult = new EtlProcessResult(
            exitCode: $result->exitCode(),
            durationSeconds: round((hrtime(true) - $startedAt) / 1_000_000_000, 3),
            lastEvent: $diagnostic['event'],
            stage: $diagnostic['stage'],
            errorType: $diagnostic['error_type'],
            errorCode: $diagnostic['error_code'],
            dbDriver: $diagnostic['db_driver'],
            connectionPhase: $diagnostic['connection_phase'],
            retryable: $diagnostic['retryable'],
            stderrPresent: trim($result->errorOutput()) !== '',
        );

        if (! $etlResult->successful()) {
            Log::warning('El proceso ETL finalizó con diagnóstico controlado.', [
                'batch_id' => $batchId,
                'exit_code' => $etlResult->exitCode,
                'ultimo_evento' => $etlResult->lastEvent,
                'stage' => $etlResult->stage,
                'error_type' => $etlResult->errorType,
                'error_code' => $etlResult->errorCode,
                'db_driver' => $etlResult->dbDriver,
                'connection_phase' => $etlResult->connectionPhase,
                'retryable' => $etlResult->retryable,
                'stderr_present' => $etlResult->stderrPresent,
            ]);
        }

        return $etlResult;
    }

    /**
     * @return array{string, string}
     */
    private function validatedConfiguration(): array
    {
        if (! config('etl.enabled')) {
            throw new EtlProcessStartFailed('No fue posible iniciar el procesador ETL.');
        }

        $pythonBinary = trim((string) config('etl.python_binary'));
        $workingDirectory = trim((string) config('etl.workdir'));

        if ($pythonBinary === '' || ! is_file($pythonBinary)) {
            throw new EtlProcessStartFailed('No fue posible iniciar el procesador ETL.');
        }

        if ($workingDirectory === '' || ! is_dir($workingDirectory)) {
            throw new EtlProcessStartFailed('No fue posible iniciar el procesador ETL.');
        }

        return [$pythonBinary, $workingDirectory];
    }

    private function withConfiguredTimeout(PendingProcess $process): PendingProcess
    {
        $timeout = max(0, (int) config('etl.process_timeout_seconds'));

        return $timeout === 0 ? $process->forever() : $process->timeout($timeout);
    }

    /**
     * @return array{event: ?string, stage: ?string, error_type: ?string, error_code: ?int, db_driver: ?string, connection_phase: ?string, retryable: ?bool}|null
     */
    private function lastJsonDiagnostic(string $output): ?array
    {
        $diagnostic = null;

        foreach (preg_split('/\R/', $output) ?: [] as $line) {
            if (trim($line) === '') {
                continue;
            }

            try {
                $payload = json_decode($line, true, flags: JSON_THROW_ON_ERROR);
            } catch (JsonException) {
                continue;
            }

            if (! is_array($payload) || ! is_string($payload['event'] ?? null)) {
                continue;
            }

            $diagnostic = [
                'event' => $this->safeText($payload['event']),
                'stage' => $this->safeText($payload['stage'] ?? null),
                'error_type' => $this->safeText($payload['error_type'] ?? null),
                'error_code' => $this->safeInteger($payload['error_code'] ?? null),
                'db_driver' => $this->safeText($payload['db_driver'] ?? null),
                'connection_phase' => $this->safeText($payload['connection_phase'] ?? null),
                'retryable' => is_bool($payload['retryable'] ?? null) ? $payload['retryable'] : null,
            ];
        }

        return $diagnostic;
    }

    private function safeText(mixed $value): ?string
    {
        if (! is_string($value) || ! preg_match('/^[A-Za-z0-9_.-]{1,120}$/', $value)) {
            return null;
        }

        return $value;
    }

    private function safeInteger(mixed $value): ?int
    {
        if (is_int($value)) {
            return $value;
        }

        if (is_string($value) && preg_match('/^[0-9]{1,9}$/', $value)) {
            return (int) $value;
        }

        return null;
    }
}
