<?php

namespace App\Services\Payments;

use Carbon\CarbonImmutable;
use Illuminate\Contracts\Pagination\Paginator;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\Collection;
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
     * @return Collection<int, object>
     */
    public function history(int $rawId): Collection
    {
        return $this->controlConnection()
            ->table(config('payments.tables.resolutions'))
            ->select([
                'id_resolucion',
                'raw_pago_id',
                'documento_anterior',
                'documento_nuevo',
                'motivo',
                'usuario',
                'fecha_modificacion',
                'activo',
            ])
            ->where('raw_pago_id', $rawId)
            ->orderByDesc('fecha_modificacion')
            ->orderByDesc('id_resolucion')
            ->get();
    }

    /**
     * @param  array<string, mixed>  $filters
     */
    public function paginateCorrections(array $filters): Paginator
    {
        $query = $this->controlConnection()
            ->table(config('payments.tables.resolutions').' as resolution')
            ->join(
                config('payments.tables.audit_current').' as payment',
                'payment.raw_id',
                '=',
                'resolution.raw_pago_id',
            )
            ->select([
                'resolution.id_resolucion',
                'resolution.raw_pago_id',
                'resolution.fecha_modificacion',
                'resolution.documento_anterior',
                'resolution.documento_nuevo',
                'resolution.usuario',
                'resolution.motivo',
                'resolution.activo',
                'payment.FECHA as fecha_pago',
                'payment.MONTO',
                'payment.OPERACION',
            ]);

        if (filled($filters['fecha_cambio_desde'] ?? null)) {
            $query->where(
                'resolution.fecha_modificacion',
                '>=',
                $this->displayDateBoundaryInUtc($filters['fecha_cambio_desde']),
            );
        }

        if (filled($filters['fecha_cambio_hasta'] ?? null)) {
            $query->where(
                'resolution.fecha_modificacion',
                '<',
                $this->displayDateBoundaryInUtc($filters['fecha_cambio_hasta'], nextDay: true),
            );
        }

        if (filled($filters['documento'] ?? null)) {
            $query->where(function (Builder $query) use ($filters): void {
                $query
                    ->where('resolution.documento_anterior', 'like', $filters['documento'].'%')
                    ->orWhere('resolution.documento_nuevo', 'like', $filters['documento'].'%');
            });
        }

        if (filled($filters['usuario'] ?? null)) {
            $query->where('resolution.usuario', 'like', $filters['usuario'].'%');
        }

        if (filled($filters['raw_pago_id'] ?? null)) {
            $query->where('resolution.raw_pago_id', (int) $filters['raw_pago_id']);
        }

        return $query
            ->orderByDesc('resolution.fecha_modificacion')
            ->orderByDesc('resolution.id_resolucion')
            ->simplePaginate($this->perPage($filters));
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

    private function controlConnection(): ConnectionInterface
    {
        return DB::connection(config('payments.control_connection'));
    }

    private function displayDateBoundaryInUtc(string $date, bool $nextDay = false): string
    {
        $boundary = CarbonImmutable::createFromFormat(
            '!Y-m-d',
            $date,
            config('app.display_timezone'),
        );

        if ($nextDay) {
            $boundary = $boundary->addDay();
        }

        return $boundary->utc()->format('Y-m-d H:i:s');
    }
}
