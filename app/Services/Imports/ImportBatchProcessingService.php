<?php

namespace App\Services\Imports;

use App\ImportStatus;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\Facades\DB;

final class ImportBatchProcessingService
{
    public function status(int $batchId): ?ImportStatus
    {
        $status = $this->connection()
            ->table(config('imports.table'))
            ->where('batch_id', $batchId)
            ->value('estado');

        return is_string($status) ? ImportStatus::tryFrom($status) : null;
    }

    public function markStartupFailure(int $batchId): bool
    {
        return $this->connection()
            ->table(config('imports.table'))
            ->where('batch_id', $batchId)
            ->where('estado', ImportStatus::Pending->value)
            ->update([
                'estado' => ImportStatus::Error->value,
                'fecha_fin' => now('UTC')->format('Y-m-d H:i:s'),
                'mensaje_error' => 'No fue posible iniciar el procesamiento.',
            ]) === 1;
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.connection'));
    }
}
