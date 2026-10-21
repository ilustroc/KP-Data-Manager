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
    private const UPSERT_SOURCE_CODE = 'BASE_TELEFONOS';

    /**
     * @return Collection<int, object>
     */
    public function activeForDataset(DatasetCode $dataset): Collection
    {
        $sources = $this->connection()
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

        foreach ($sources as $source) {
            if ($dataset !== DatasetCode::Telefonos || $source->source_code !== self::UPSERT_SOURCE_CODE) {
                $source->allows_upsert = 0;
            }
        }

        return $sources;
    }

    public function requireAllowed(
        DatasetCode $dataset,
        SearchSourceCode $source,
        RefreshMode $refreshMode,
    ): object {
        if ($refreshMode === RefreshMode::Upsert
            && ($dataset !== DatasetCode::Telefonos || $source->value !== self::UPSERT_SOURCE_CODE)) {
            throw new SearchImportConfigurationException(
                'UPSERT está autorizado únicamente para TELEFONOS / BASE_TELEFONOS.',
            );
        }

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
