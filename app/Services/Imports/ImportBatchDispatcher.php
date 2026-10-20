<?php

namespace App\Services\Imports;

use App\Jobs\ProcessImportBatch;
use Illuminate\Bus\UniqueLock;
use Illuminate\Contracts\Cache\Repository as CacheRepository;
use Illuminate\Support\Facades\Log;
use Throwable;

final class ImportBatchDispatcher
{
    public function __construct(
        private readonly CacheRepository $cache,
        private readonly ImportFileAccessService $fileAccess,
    ) {}

    public function dispatch(int $batchId): void
    {
        $job = new ProcessImportBatch($batchId);

        try {
            if ((bool) config('imports.private_files.enforce_before_dispatch')) {
                $this->fileAccess->prepareBatch($batchId);
            }
            $pendingDispatch = dispatch($job);
            unset($pendingDispatch);
        } catch (Throwable $exception) {
            $this->releaseUniqueLock($job, $batchId);

            Log::error('No fue posible encolar el procesamiento ETL.', [
                'batch_id' => $batchId,
                'exception_type' => $exception::class,
            ]);

            throw new ImportDispatchFailed('No fue posible enviar la carga a procesamiento.');
        }
    }

    private function releaseUniqueLock(ProcessImportBatch $job, int $batchId): void
    {
        try {
            (new UniqueLock($this->cache))->release($job);
        } catch (Throwable $exception) {
            Log::warning('No fue posible liberar el bloqueo de una carga no encolada.', [
                'batch_id' => $batchId,
                'exception_type' => $exception::class,
            ]);
        }
    }
}
