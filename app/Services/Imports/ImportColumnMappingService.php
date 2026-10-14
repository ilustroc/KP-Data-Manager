<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\SearchSourceCode;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

final class ImportColumnMappingService
{
    /**
     * @return Collection<int, object>
     */
    public function forVersion(
        DatasetCode $dataset,
        SearchSourceCode $source,
        int $mappingVersion,
    ): Collection {
        if ($mappingVersion < 1) {
            throw new SearchImportConfigurationException('mapping_version debe ser mayor que cero.');
        }

        $mappings = $this->connection()
            ->table($this->mappingTable())
            ->select([
                'mapping_id',
                'source_position',
                'source_column',
                'target_column',
                'is_required',
                'transformation',
                'default_value',
            ])
            ->where('dataset_code', $dataset->value)
            ->where('source_code', $source->value)
            ->where('mapping_version', $mappingVersion)
            ->where('is_active', 1)
            ->orderBy('source_position')
            ->get();

        if ($mappings->isEmpty()) {
            throw new SearchImportConfigurationException(
                "No existe mapping activo v{$mappingVersion} para {$dataset->value} / {$source->value}.",
            );
        }

        return $mappings;
    }

    /**
     * @return Collection<int, object>
     */
    public function current(DatasetCode $dataset, SearchSourceCode $source): Collection
    {
        $mappingVersion = $this->connection()
            ->table($this->datasetSourceTable())
            ->where('dataset_code', $dataset->value)
            ->where('source_code', $source->value)
            ->where('is_active', 1)
            ->value('current_mapping_version');

        if (! is_int($mappingVersion) && ! ctype_digit((string) $mappingVersion)) {
            throw new SearchImportConfigurationException(
                "No hay una versión de mapping vigente para {$dataset->value} / {$source->value}.",
            );
        }

        return $this->forVersion($dataset, $source, (int) $mappingVersion);
    }

    private function mappingTable(): string
    {
        return (string) config('imports.search.tables.column_mappings');
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
