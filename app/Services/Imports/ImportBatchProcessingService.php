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

    public function markFailedIfNonTerminal(int $batchId): bool
    {
        return $this->connection()
            ->table(config('imports.table'))
            ->where('batch_id', $batchId)
            ->whereIn('estado', [
                ImportStatus::Pending->value,
                ImportStatus::Processing->value,
            ])
            ->update([
                'estado' => ImportStatus::Error->value,
                'fecha_fin' => now('UTC')->format('Y-m-d H:i:s'),
                'mensaje_error' => 'El procesamiento ETL terminó con error. Revisa el log técnico.',
            ]) === 1;
    }

    public function markSearchRecoveryFailureIfProcessing(int $batchId): bool
    {
        return $this->connection()
            ->table(config('imports.table'))
            ->where('batch_id', $batchId)
            ->where('estado', ImportStatus::Processing->value)
            ->update([
                'estado' => ImportStatus::Error->value,
                'fecha_fin' => now('UTC')->format('Y-m-d H:i:s'),
                'mensaje_error' => 'No fue posible recuperar la publicación Gold SEARCH. Revisa el log técnico.',
            ]) === 1;
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.connection'));
    }
}
