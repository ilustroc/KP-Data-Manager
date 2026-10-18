<?php

namespace App\Services\Imports;

use App\DatasetCode;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

final class SearchDatasetCatalogService
{
    /**
     * @return Collection<int, object>
     */
    public function active(): Collection
    {
        return $this->connection()
            ->table($this->table())
            ->select(['dataset_code', 'label', 'description', 'sort_order'])
            ->where('is_active', 1)
            ->orderBy('sort_order')
            ->orderBy('dataset_code')
            ->get();
    }

    public function find(DatasetCode $dataset): ?object
    {
        return $this->connection()
            ->table($this->table())
            ->select(['dataset_code', 'label', 'description', 'sort_order', 'is_active'])
            ->where('dataset_code', $dataset->value)
            ->first();
    }

    public function requireActive(DatasetCode $dataset): object
    {
        $definition = $this->find($dataset);

        if ($definition === null || (int) $definition->is_active !== 1) {
            throw new SearchImportConfigurationException(
                "El dataset {$dataset->value} no existe o no está habilitado.",
            );
        }

        return $definition;
    }

    private function table(): string
    {
        return (string) config('imports.search.tables.datasets');
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.search.control_connection'));
    }
}
