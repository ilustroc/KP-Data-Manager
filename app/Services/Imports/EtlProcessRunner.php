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
    /**
     * @var list<string>
     */
    private const SEARCH_METRIC_PHASES = [
        'parse_normalize',
        'bronze_insert',
        'bronze_id_lookup',
        'silver_insert',
        'scope_lookup',
        'scope_insert',
        'dedup_lookup',
        'preflight',
        'gold_source_validation',
        'gold_insert',
        'gold_delete',
        'integrity_validation',
        'batch_final_lock',
        'batch_finalize',
        'commit',
        'total',
    ];

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

        $this->persistSearchPhaseMetrics($result->output(), $batchId);

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

    private function persistSearchPhaseMetrics(string $output, int $batchId): void
    {
        foreach (preg_split('/\R/', $output) ?: [] as $line) {
            if (trim($line) === '') {
                continue;
            }

            try {
                $payload = json_decode($line, true, flags: JSON_THROW_ON_ERROR);
            } catch (JsonException) {
                continue;
            }

            if (! is_array($payload) || ($payload['event'] ?? null) !== 'search_phase_metric') {
                continue;
            }

            $metric = $this->safeSearchPhaseMetric($payload, $batchId);
            if ($metric !== null) {
                Log::info('search_phase_metric', $metric);
            }
        }
    }

    /**
     * @param  array<string, mixed>  $payload
     * @return array{batch_id: int, dataset_code: string, refresh_mode: string, phase: string, duration_seconds: float, rows_processed: int, rows_per_second: float, logical_statement_count: int, executemany_calls: int, physical_statement_count: int, invocations: int, peak_memory_mb: ?float, successful: bool, last_phase: ?string, failed_phase: ?string}|null
     */
    private function safeSearchPhaseMetric(array $payload, int $batchId): ?array
    {
        $datasetCode = $this->safeText($payload['dataset_code'] ?? null);
        $refreshMode = $this->safeText($payload['refresh_mode'] ?? null);
        $phase = $this->safeMetricPhase($payload['phase'] ?? null);
        $durationSeconds = $this->safeNonNegativeFloat($payload['duration_seconds'] ?? null);
        $rowsProcessed = $this->safeNonNegativeInteger($payload['rows_processed'] ?? null);
        $rowsPerSecond = $this->safeNonNegativeFloat($payload['rows_per_second'] ?? null);
        $logicalStatementCount = $this->safeNonNegativeInteger(
            $payload['logical_statement_count'] ?? null,
        );
        $executemanyCalls = $this->safeNonNegativeInteger($payload['executemany_calls'] ?? null);
        $physicalStatementCount = $this->safeNonNegativeInteger(
            $payload['physical_statement_count'] ?? null,
        );
        $invocations = $this->safeNonNegativeInteger($payload['invocations'] ?? null);
        $peakMemoryValue = $payload['peak_memory_mb'] ?? null;
        $peakMemoryMb = $peakMemoryValue === null
            ? null
            : $this->safeNonNegativeFloat($peakMemoryValue);
        $successful = $payload['successful'] ?? null;

        if (
            $datasetCode === null
            || $refreshMode === null
            || $phase === null
            || $durationSeconds === null
            || $rowsProcessed === null
            || $rowsPerSecond === null
            || $logicalStatementCount === null
            || $executemanyCalls === null
            || $physicalStatementCount === null
            || $invocations === null
            || ($peakMemoryValue !== null && $peakMemoryMb === null)
            || ! is_bool($successful)
        ) {
            return null;
        }

        return [
            'batch_id' => $batchId,
            'dataset_code' => $datasetCode,
            'refresh_mode' => $refreshMode,
            'phase' => $phase,
            'duration_seconds' => $durationSeconds,
            'rows_processed' => $rowsProcessed,
            'rows_per_second' => $rowsPerSecond,
            'logical_statement_count' => $logicalStatementCount,
            'executemany_calls' => $executemanyCalls,
            'physical_statement_count' => $physicalStatementCount,
            'invocations' => $invocations,
            'peak_memory_mb' => $peakMemoryMb,
            'successful' => $successful,
            'last_phase' => $this->safeMetricPhase($payload['last_phase'] ?? null),
            'failed_phase' => $this->safeMetricPhase($payload['failed_phase'] ?? null),
        ];
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

    private function safeMetricPhase(mixed $value): ?string
    {
        return is_string($value) && in_array($value, self::SEARCH_METRIC_PHASES, true)
            ? $value
            : null;
    }

    private function safeNonNegativeInteger(mixed $value): ?int
    {
        return is_int($value) && $value >= 0 ? $value : null;
    }

    private function safeNonNegativeFloat(mixed $value): ?float
    {
        if (! is_int($value) && ! is_float($value)) {
            return null;
        }

        $number = (float) $value;

        return is_finite($number) && $number >= 0 ? $number : null;
    }
}
