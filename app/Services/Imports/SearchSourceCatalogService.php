<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;
use App\SearchSourceCode;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

final class SearchSourceCatalogService
{
    /**
     * @return Collection<int, object>
     */
    public function activeForDataset(DatasetCode $dataset): Collection
    {
        return $this->connection()
            ->table($this->datasetSourceTable().' as dataset_source')
            ->join(
                $this->sourceTable().' as source',
                'source.source_code',
                '=',
                'dataset_source.source_code',
            )
            ->select([
                'source.source_code',
                'source.label',
                'source.description',
                'dataset_source.default_refresh_mode',
                'dataset_source.allows_full_replace',
                'dataset_source.allows_scope_replace',
                'dataset_source.allows_upsert',
                'dataset_source.current_mapping_version',
            ])
            ->where('dataset_source.dataset_code', $dataset->value)
            ->where('dataset_source.is_active', 1)
            ->where('source.is_active', 1)
            ->orderBy('source.label')
            ->orderBy('source.source_code')
            ->get();
    }

    public function requireAllowed(
        DatasetCode $dataset,
        SearchSourceCode $source,
        RefreshMode $refreshMode,
    ): object {
        $definition = $this->connection()
            ->table($this->datasetSourceTable().' as dataset_source')
            ->join(
                $this->sourceTable().' as source',
                'source.source_code',
                '=',
                'dataset_source.source_code',
            )
            ->select([
                'dataset_source.dataset_code',
                'dataset_source.source_code',
                'dataset_source.default_refresh_mode',
                'dataset_source.allows_full_replace',
                'dataset_source.allows_scope_replace',
                'dataset_source.allows_upsert',
                'dataset_source.current_mapping_version',
            ])
            ->where('dataset_source.dataset_code', $dataset->value)
            ->where('dataset_source.source_code', $source->value)
            ->where('dataset_source.is_active', 1)
            ->where('source.is_active', 1)
            ->first();

        if ($definition === null) {
            throw new SearchImportConfigurationException(
                "La fuente {$source->value} no está habilitada para {$dataset->value}.",
            );
        }

        $permissionColumn = $refreshMode->permissionColumn();

        if ((int) $definition->{$permissionColumn} !== 1) {
            throw new SearchImportConfigurationException(
                "El modo {$refreshMode->value} no está habilitado para {$dataset->value} / {$source->value}.",
            );
        }

        return $definition;
    }

    private function sourceTable(): string
    {
        return (string) config('imports.search.tables.sources');
    }

    private function datasetSourceTable(): string
    {
        return (string) config('imports.search.tables.dataset_sources');
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.search.control_connection'));
    }
}
