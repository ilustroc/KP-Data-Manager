<?php

namespace App\Jobs;

use App\ImportStatus;
use App\Services\Imports\EtlProcessFailed;
use App\Services\Imports\EtlProcessRunner;
use App\Services\Imports\EtlProcessStartFailed;
use App\Services\Imports\ImportBatchProcessingService;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Facades\Log;
use Throwable;

class ProcessImportBatch implements ShouldBeUnique, ShouldQueue
{
    use Queueable;

    public int $tries = 1;

    public int $timeout;

    public bool $failOnTimeout = true;

    public function __construct(public readonly int $batchId)
    {
        $this->timeout = max(0, (int) config('etl.job_timeout_seconds'));
        $this->onQueue((string) config('etl.queue'));
    }

    public function handle(
        ImportBatchProcessingService $batches,
        EtlProcessRunner $runner,
    ): void {
        if ($batches->status($this->batchId) !== ImportStatus::Pending) {
            Log::info('Procesamiento ETL omitido porque el batch ya no está pendiente.', [
                'batch_id' => $this->batchId,
            ]);

            return;
        }

        try {
            $result = $runner->run($this->batchId);
        } catch (EtlProcessStartFailed $exception) {
            $batches->markStartupFailure($this->batchId);

            Log::error('No fue posible iniciar el procesador ETL.', [
                'batch_id' => $this->batchId,
            ]);

            throw $exception;
        }

        $batchStatus = $batches->status($this->batchId);

        Log::info('Proceso ETL finalizado.', [
            'batch_id' => $this->batchId,
            'exit_code' => $result->exitCode,
            'duracion_segundos' => $result->durationSeconds,
            'ultimo_evento' => $result->lastEvent,
            'stage' => $result->stage,
            'error_type' => $result->errorType,
            'error_code' => $result->errorCode,
            'db_driver' => $result->dbDriver,
            'connection_phase' => $result->connectionPhase,
            'retryable' => $result->retryable,
            'stderr_present' => $result->stderrPresent,
            'estado_batch' => $batchStatus?->value,
        ]);

        if (! $result->successful()) {
            throw new EtlProcessFailed('El procesador ETL finalizó con error.');
        }
    }

    public function uniqueId(): string
    {
        return (string) $this->batchId;
    }

    public function failed(?Throwable $exception): void
    {
        $markedError = app(ImportBatchProcessingService::class)
            ->markFailedIfNonTerminal($this->batchId);

        Log::error('El job de procesamiento ETL terminó sin reintento automático.', [
            'batch_id' => $this->batchId,
            'exception_type' => $exception === null ? null : $exception::class,
            'batch_marked_error' => $markedError,
        ]);
    }
}
