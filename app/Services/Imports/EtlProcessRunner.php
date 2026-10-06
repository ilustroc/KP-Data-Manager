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
        [$pythonBinary, $workingDirectory] = $this->validatedConfiguration();
        $command = [
            $pythonBinary,
            '-m',
            'src.worker',
            '--batch-id',
            (string) $batchId,
        ];
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

        return new EtlProcessResult(
            exitCode: $result->exitCode(),
            durationSeconds: round((hrtime(true) - $startedAt) / 1_000_000_000, 3),
            lastEvent: $this->lastJsonEvent($result->output()),
        );
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

    private function lastJsonEvent(string $output): ?string
    {
        $lastEvent = null;

        foreach (preg_split('/\R/', $output) ?: [] as $line) {
            if (trim($line) === '') {
                continue;
            }

            try {
                $payload = json_decode($line, true, flags: JSON_THROW_ON_ERROR);
            } catch (JsonException) {
                continue;
            }

            if (is_array($payload) && is_string($payload['event'] ?? null)) {
                $lastEvent = $payload['event'];
            }
        }

        return $lastEvent;
    }
}
