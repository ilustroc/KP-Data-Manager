<?php

namespace App\Console\Commands;

use App\Services\Imports\EtlProcessRunner;
use App\Services\Imports\ImportBatchProcessingService;
use Illuminate\Console\Command;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\Log;
use Throwable;

class RecoverSearchPublish extends Command
{
    protected $signature = 'imports:recover-search-publish {batch_id : ID del batch SEARCH ya validado}';

    protected $description = 'Publica solamente Gold desde un batch SEARCH ya validado.';

    /**
     * Execute the console command.
     */
    public function handle(
        EtlProcessRunner $runner,
        ImportBatchProcessingService $batches,
    ): int {
        $batchId = filter_var($this->argument('batch_id'), FILTER_VALIDATE_INT, [
            'options' => ['min_range' => 1],
        ]);
        if (! is_int($batchId)) {
            $this->error('El batch_id debe ser un entero positivo.');

            return self::FAILURE;
        }

        $result = $runner->runPublishOnly($batchId);
        if (! $result->successful()) {
            try {
                $batches->markSearchRecoveryFailureIfProcessing($batchId);
            } catch (Throwable $exception) {
                Log::error('No fue posible marcar ERROR después de un fallo de recuperación SEARCH.', [
                    'batch_id' => $batchId,
                    'exception_class' => $exception::class,
                    'sqlstate' => $this->safeSqlState($exception),
                    'error_code' => $this->safeDriverErrorCode($exception),
                    'fallback_mark_error_failed' => true,
                ]);

                $this->error('No fue posible publicar Gold desde el batch SEARCH. El estado del batch no pudo actualizarse automáticamente. Revisa el log técnico.');

                return self::FAILURE;
            }
            $this->error('No fue posible publicar Gold desde el batch SEARCH. Revisa el log técnico.');

            return self::FAILURE;
        }

        $this->info('Publicación Gold recuperada correctamente.');

        return self::SUCCESS;
    }

    private function safeSqlState(Throwable $exception): ?string
    {
        if (! $exception instanceof QueryException || ! is_array($exception->errorInfo ?? null)) {
            return null;
        }

        $sqlState = $exception->errorInfo[0] ?? null;

        return is_string($sqlState) && preg_match('/^[A-Z0-9]{5}$/', $sqlState) ? $sqlState : null;
    }

    private function safeDriverErrorCode(Throwable $exception): ?int
    {
        if (! $exception instanceof QueryException || ! is_array($exception->errorInfo ?? null)) {
            return null;
        }

        $errorCode = $exception->errorInfo[1] ?? null;
        if (is_int($errorCode)) {
            return $errorCode;
        }

        return is_string($errorCode) && preg_match('/^[0-9]{1,9}$/', $errorCode)
            ? (int) $errorCode
            : null;
    }
}
