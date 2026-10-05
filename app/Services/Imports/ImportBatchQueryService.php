<?php

namespace App\Services\Imports;

use Carbon\CarbonImmutable;
use Illuminate\Contracts\Pagination\Paginator;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\Facades\DB;

class ImportBatchQueryService
{
    /**
     * @param  array<string, mixed>  $filters
     */
    public function paginate(array $filters): Paginator
    {
        $query = $this->connection()->table(config('imports.table'));

        $this->applyFilters($query, $filters);

        return $query
            ->orderByDesc('batch_id')
            ->simplePaginate($this->perPage($filters))
            ->withQueryString();
    }

    public function find(int $batchId): ?object
    {
        return $this->connection()
            ->table(config('imports.table'))
            ->where('batch_id', $batchId)
            ->first();
    }

    public function paginateErrors(int $batchId): Paginator
    {
        return $this->connection()
            ->table(config('imports.error_table'))
            ->where('batch_id', $batchId)
            ->orderBy('numero_fila')
            ->orderBy('id')
            ->simplePaginate(
                (int) config('imports.pagination.errors'),
                ['*'],
                'errores_pagina',
            )
            ->withQueryString();
    }

    /**
     * @param  array<string, mixed>  $filters
     */
    private function applyFilters(Builder $query, array $filters): void
    {
        if (filled($filters['batch_id'] ?? null)) {
            $query->where('batch_id', (int) $filters['batch_id']);
        }

        foreach (['tipo', 'origen', 'estado'] as $filter) {
            if (filled($filters[$filter] ?? null)) {
                $query->where($filter, $filters[$filter]);
            }
        }

        if (filled($filters['nombre_archivo'] ?? null)) {
            $query->where('archivo_original', 'like', '%'.$filters['nombre_archivo'].'%');
        }

        if (filled($filters['usuario'] ?? null)) {
            $query->where('usuario', 'like', $filters['usuario'].'%');
        }

        if (filled($filters['fecha_desde'] ?? null)) {
            $query->where('fecha_inicio', '>=', $this->displayDateBoundaryInUtc($filters['fecha_desde']));
        }

        if (filled($filters['fecha_hasta'] ?? null)) {
            $query->where('fecha_inicio', '<', $this->displayDateBoundaryInUtc(
                $filters['fecha_hasta'],
                nextDay: true,
            ));
        }
    }

    /**
     * @param  array<string, mixed>  $filters
     */
    private function perPage(array $filters): int
    {
        $perPage = (int) ($filters['per_page'] ?? config('imports.pagination.default'));

        return in_array($perPage, config('imports.pagination.allowed'), true)
            ? $perPage
            : (int) config('imports.pagination.default');
    }

    private function displayDateBoundaryInUtc(string $date, bool $nextDay = false): string
    {
        $boundary = CarbonImmutable::createFromFormat('!Y-m-d', $date, config('app.display_timezone'));

        if ($nextDay) {
            $boundary = $boundary->addDay();
        }

        return $boundary->utc()->format('Y-m-d H:i:s');
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.connection'));
    }
}
