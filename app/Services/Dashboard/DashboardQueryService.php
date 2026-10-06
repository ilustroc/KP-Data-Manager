<?php

namespace App\Services\Dashboard;

use App\ImportStatus;
use Carbon\CarbonImmutable;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

class DashboardQueryService
{
    /**
     * @return array{cargas_hoy: int, filas_cargadas_hoy: int, con_observaciones: int, en_proceso: int}
     */
    public function summary(): array
    {
        [$startUtc, $endUtc] = $this->currentDisplayDayInUtc();

        $summary = $this->connection()
            ->table(config('imports.table'))
            ->where('fecha_inicio', '>=', $startUtc)
            ->where('fecha_inicio', '<', $endUtc)
            ->selectRaw('COUNT(*) as cargas_hoy')
            ->selectRaw('COALESCE(SUM(filas_insertadas), 0) as filas_cargadas_hoy')
            ->selectRaw(
                'COALESCE(SUM(CASE WHEN estado = ? THEN 1 ELSE 0 END), 0) as con_observaciones',
                [ImportStatus::CompletedWithErrors->value],
            )
            ->selectRaw(
                'COALESCE(SUM(CASE WHEN estado IN (?, ?, ?, ?) THEN 1 ELSE 0 END), 0) as en_proceso',
                [
                    ImportStatus::Received->value,
                    ImportStatus::Validating->value,
                    ImportStatus::Pending->value,
                    ImportStatus::Processing->value,
                ],
            )
            ->first();

        return [
            'cargas_hoy' => (int) ($summary->cargas_hoy ?? 0),
            'filas_cargadas_hoy' => (int) ($summary->filas_cargadas_hoy ?? 0),
            'con_observaciones' => (int) ($summary->con_observaciones ?? 0),
            'en_proceso' => (int) ($summary->en_proceso ?? 0),
        ];
    }

    /**
     * @return Collection<int, object>
     */
    public function recentImports(): Collection
    {
        $imports = $this->connection()
            ->table(config('imports.table'))
            ->select([
                'batch_id',
                'archivo',
                'archivo_original',
                'estado',
                'filas_insertadas',
                'filas_error',
                'fecha_inicio',
            ])
            ->orderByDesc('batch_id')
            ->limit(5)
            ->get();

        return $imports;
    }

    /**
     * @return array{string, string}
     */
    private function currentDisplayDayInUtc(): array
    {
        $start = CarbonImmutable::now(config('app.display_timezone'))->startOfDay();

        return [
            $start->utc()->format('Y-m-d H:i:s'),
            $start->addDay()->utc()->format('Y-m-d H:i:s'),
        ];
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.connection'));
    }
}
