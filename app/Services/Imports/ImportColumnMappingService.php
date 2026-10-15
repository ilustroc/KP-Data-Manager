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
     * @param  list<string>  $headers
     * @param  array<string, string>  $mapping
     */
    public function createOrReuse(
        DatasetCode $dataset,
        SearchSourceCode $source,
        array $headers,
        array $mapping,
        string $transformation,
    ): int {
        return $this->connection()->transaction(function () use ($dataset, $source, $headers, $mapping, $transformation): int {
            $datasetSource = $this->connection()
                ->table($this->datasetSourceTable())
                ->where('dataset_code', $dataset->value)
                ->where('source_code', $source->value)
                ->lockForUpdate()
                ->first();

            if ($datasetSource === null) {
                throw new SearchImportConfigurationException('La combinación dataset/fuente no está registrada.');
            }

            $currentVersion = $datasetSource->current_mapping_version === null
                ? null
                : (int) $datasetSource->current_mapping_version;
            if ($currentVersion !== null && $this->mappingMatches($dataset, $source, $currentVersion, $headers, $mapping)) {
                return $currentVersion;
            }

            $nextVersion = (int) $this->connection()
                ->table($this->mappingTable())
                ->where('dataset_code', $dataset->value)
                ->where('source_code', $source->value)
                ->max('mapping_version') + 1;
            $now = now('UTC')->format('Y-m-d H:i:s');
            $positions = array_flip($headers);
            $rows = [];
            foreach ($mapping as $target => $sourceHeader) {
                $rows[] = [
                    'dataset_code' => $dataset->value,
                    'source_code' => $source->value,
                    'mapping_version' => $nextVersion,
                    'source_position' => $positions[$sourceHeader] + 1,
                    'source_column' => $sourceHeader,
                    'target_column' => $target,
                    'is_required' => $target === 'documento',
                    'transformation' => $transformation,
                    'default_value' => null,
                    'is_active' => 1,
                    'created_at' => $now,
                    'updated_at' => $now,
                ];
            }
            $this->connection()->table($this->mappingTable())->insert($rows);
            $this->connection()->table($this->datasetSourceTable())
                ->where('dataset_code', $dataset->value)
                ->where('source_code', $source->value)
                ->update(['current_mapping_version' => $nextVersion, 'updated_at' => $now]);

            return $nextVersion;
        });
    }

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

    /**
     * @param  list<string>  $headers
     * @param  array<string, string>  $mapping
     */
    private function mappingMatches(
        DatasetCode $dataset,
        SearchSourceCode $source,
        int $version,
        array $headers,
        array $mapping,
    ): bool {
        $existing = $this->forVersion($dataset, $source, $version);
        if ($existing->count() !== count($mapping)) {
            return false;
        }
        $positions = array_flip($headers);

        return $existing->every(static function (object $row) use ($mapping, $positions): bool {
            $sourceHeader = $mapping[$row->target_column] ?? null;

            return $sourceHeader === $row->source_column
                && isset($positions[$sourceHeader])
                && (int) $row->source_position === $positions[$sourceHeader] + 1;
        });
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
