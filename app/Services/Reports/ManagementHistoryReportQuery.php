<?php

namespace App\Services\Reports;

use Illuminate\Database\DatabaseManager;
use Illuminate\Database\Query\Builder;
use Illuminate\Support\LazyCollection;

class ManagementHistoryReportQuery
{
    public function __construct(
        private readonly DatabaseManager $database,
    ) {}

    public function builder(ManagementHistoryReportPeriod $period): Builder
    {
        $connection = (string) config('reports.management_history.connection', 'mysql_control');
        $table = (string) config(
            'reports.management_history.table',
            'kpinvest_konnexia.cob_gestiones',
        );

        return $this->database
            ->connection($connection)
            ->table($table)
            ->select([
                'created_at',
                'nombre_cliente',
                'documento',
                'telefono',
                'agente_nombre',
                'canal',
                'tipificacion_n1',
                'tipificacion_n2',
                'tipificacion_n3',
                'resultado',
                'comentario',
            ])
            ->selectRaw('COALESCE(duracion_seg, 0) AS duracion')
            ->selectRaw(
                "CASE WHEN promesa_id IS NOT NULL OR fecha_promesa IS NOT NULL OR COALESCE(monto_promesa, 0) > 0 THEN 'Si' ELSE 'No' END AS promesa",
            )
            ->selectRaw('COALESCE(monto_promesa, 0) AS monto')
            ->where('created_at', '>=', $period->startUtc->format('Y-m-d H:i:s'))
            ->where('created_at', '<', $period->endExclusiveUtc->format('Y-m-d H:i:s'))
            ->orderByDesc('created_at');
    }

    public function cursor(ManagementHistoryReportPeriod $period): LazyCollection
    {
        return $this->builder($period)->cursor();
    }
}
