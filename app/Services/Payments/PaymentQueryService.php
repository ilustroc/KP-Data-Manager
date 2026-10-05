<?php

namespace App\Services\Payments;

use Illuminate\Contracts\Pagination\Paginator;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\Facades\DB;

class PaymentQueryService
{
    /** @var list<string> */
    private const PAYMENT_COLUMNS = [
        'raw_id',
        'FECHA',
        'DOCUMENTO',
        'MONTO',
        'ACUMULADO',
        'RECAUDO',
        'OPERACION',
        'COMENTARIO',
        'HORA',
        'source_file',
        'batch_id',
        'ingested_at',
    ];

    /**
     * @param  array<string, mixed>  $filters
     */
    public function paginateCurrent(array $filters): Paginator
    {
        return $this->paginate(
            $this->connection()->table(config('payments.views.current')),
            $filters,
            applyStatusFilter: true,
        );
    }

    /**
     * @param  array<string, mixed>  $filters
     */
    public function paginateUnidentified(array $filters): Paginator
    {
        return $this->paginate(
            $this->connection()->table(config('payments.views.unidentified')),
            $filters,
            applyStatusFilter: false,
        );
    }

    public function find(int $rawId): ?object
    {
        return $this->connection()
            ->table(config('payments.views.current'))
            ->select(self::PAYMENT_COLUMNS)
            ->where('raw_id', $rawId)
            ->first();
    }

    /**
     * @param  array<string, mixed>  $filters
     */
    private function paginate(Builder $query, array $filters, bool $applyStatusFilter): Paginator
    {
        $this->applyFilters($query, $filters, $applyStatusFilter);

        return $query
            ->select(self::PAYMENT_COLUMNS)
            ->orderByDesc('FECHA')
            ->orderByDesc('HORA')
            ->orderByDesc('raw_id')
            ->simplePaginate($this->perPage($filters));
    }

    /**
     * @param  array<string, mixed>  $filters
     */
    private function applyFilters(Builder $query, array $filters, bool $applyStatusFilter): void
    {
        if (filled($filters['fecha_desde'] ?? null)) {
            $query->where('FECHA', '>=', $filters['fecha_desde']);
        }

        if (filled($filters['fecha_hasta'] ?? null)) {
            $query->where('FECHA', '<=', $filters['fecha_hasta']);
        }

        if (filled($filters['documento'] ?? null)) {
            $query->where('DOCUMENTO', 'like', $filters['documento'].'%');
        }

        if (filled($filters['operacion'] ?? null)) {
            $query->where('OPERACION', 'like', $filters['operacion'].'%');
        }

        if (filled($filters['recaudo'] ?? null)) {
            $query->where('RECAUDO', $filters['recaudo']);
        }

        if (filled($filters['monto_min'] ?? null)) {
            $query->where('MONTO', '>=', $filters['monto_min']);
        }

        if (filled($filters['monto_max'] ?? null)) {
            $query->where('MONTO', '<=', $filters['monto_max']);
        }

        if (! $applyStatusFilter) {
            return;
        }

        match ($filters['estado'] ?? 'todos') {
            'identificados' => $query
                ->whereNotNull('DOCUMENTO')
                ->whereRaw("TRIM(DOCUMENTO) <> ''"),
            'sin_identificar' => $query->where(function (Builder $query): void {
                $query
                    ->whereNull('DOCUMENTO')
                    ->orWhereRaw("TRIM(DOCUMENTO) = ''");
            }),
            default => null,
        };
    }

    /**
     * @param  array<string, mixed>  $filters
     */
    private function perPage(array $filters): int
    {
        $perPage = (int) ($filters['per_page'] ?? config('payments.pagination.default'));

        return in_array($perPage, config('payments.pagination.allowed'), true)
            ? $perPage
            : (int) config('payments.pagination.default');
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('payments.connection'));
    }
}
