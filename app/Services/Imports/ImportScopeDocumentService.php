<?php

namespace App\Services\Imports;

use App\ImportType;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\Facades\DB;

final class ImportScopeDocumentService
{
    /**
     * Reemplaza de forma atómica el scope oficial de un batch SEARCH.
     *
     * @param  iterable<mixed>  $documents
     */
    public function replaceForBatch(int $batchId, iterable $documents): int
    {
        if ($batchId < 1) {
            throw new SearchImportConfigurationException('batch_id debe ser mayor que cero.');
        }

        return $this->connection()->transaction(function () use ($batchId, $documents): int {
            $batch = $this->connection()
                ->table(config('imports.table'))
                ->select(['batch_id', 'tipo'])
                ->where('batch_id', $batchId)
                ->lockForUpdate()
                ->first();

            if ($batch === null || $batch->tipo !== ImportType::Search->value) {
                throw new SearchImportConfigurationException(
                    "El batch #{$batchId} no existe o no pertenece al dominio SEARCH.",
                );
            }

            $this->connection()
                ->table($this->scopeTable())
                ->where('batch_id', $batchId)
                ->delete();

            $chunk = [];
            $chunkSize = max(1, (int) config('imports.search.scope_insert_chunk_size', 1000));
            $createdAt = now('UTC')->format('Y-m-d H:i:s');

            foreach ($documents as $document) {
                $normalized = $this->normalizeDocument($document);
                $chunk[$normalized] = [
                    'batch_id' => $batchId,
                    'documento' => $normalized,
                    'created_at' => $createdAt,
                ];

                if (count($chunk) >= $chunkSize) {
                    $this->insertChunk(array_values($chunk));
                    $chunk = [];
                }
            }

            if ($chunk !== []) {
                $this->insertChunk(array_values($chunk));
            }

            $scopeCount = $this->countForBatch($batchId);

            $this->connection()
                ->table(config('imports.table'))
                ->where('batch_id', $batchId)
                ->update(['scope_count' => $scopeCount]);

            return $scopeCount;
        }, 3);
    }

    public function countForBatch(int $batchId): int
    {
        return $this->connection()
            ->table($this->scopeTable())
            ->where('batch_id', $batchId)
            ->count();
    }

    /**
     * @param  array<int, array{batch_id: int, documento: string, created_at: string}>  $rows
     */
    private function insertChunk(array $rows): void
    {
        $this->connection()
            ->table($this->scopeTable())
            ->upsert($rows, ['batch_id', 'documento'], ['documento']);
    }

    private function normalizeDocument(mixed $document): string
    {
        if (! is_string($document) && ! is_int($document)) {
            throw new SearchImportConfigurationException(
                'Cada documento del scope debe ser texto o entero, sin valores vacíos.',
            );
        }

        $normalized = trim((string) $document);

        if ($normalized === '' || mb_strlen($normalized) > 100) {
            throw new SearchImportConfigurationException(
                'Cada documento del scope debe contener entre 1 y 100 caracteres.',
            );
        }

        return $normalized;
    }

    private function scopeTable(): string
    {
        return (string) config('imports.search.tables.scope_documents');
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.search.control_connection'));
    }
}
