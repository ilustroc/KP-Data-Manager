<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\ManagementHistoryReportPeriod;
use App\Services\Reports\ManagementHistoryReportQuery;
use Carbon\CarbonImmutable;
use Illuminate\Database\DatabaseManager;
use Tests\TestCase;

class ManagementHistoryReportQueryTest extends TestCase
{
    public function test_uses_select_only_bindings_and_index_friendly_utc_bounds(): void
    {
        config([
            'reports.management_history.connection' => 'sqlite',
            'reports.management_history.table' => 'cob_gestiones',
            'reports.management_history.timezone' => 'America/Lima',
            'reports.management_history.source_timezone' => 'UTC',
        ]);
        $period = ManagementHistoryReportPeriod::forExecution(
            CarbonImmutable::parse('2026-10-09 10:00:00', 'America/Lima'),
        );

        $builder = (new ManagementHistoryReportQuery(app(DatabaseManager::class)))->builder($period);
        $sql = mb_strtolower($builder->toSql());

        $this->assertStringStartsWith('select ', $sql);
        $this->assertStringNotContainsString('select *', $sql);
        $this->assertStringContainsString('coalesce(duracion_seg, 0)', $sql);
        $this->assertStringContainsString('promesa_id is not null', $sql);
        $this->assertStringContainsString('fecha_promesa is not null', $sql);
        $this->assertStringContainsString('coalesce(monto_promesa, 0) > 0', $sql);
        $this->assertStringContainsString('order by "created_at" desc', $sql);
        $this->assertStringNotContainsString('date_sub', $sql);
        $this->assertStringNotContainsString('insert ', $sql);
        $this->assertStringNotContainsString('update ', $sql);
        $this->assertStringNotContainsString('delete ', $sql);
        $this->assertSame([
            '2025-10-01 05:00:00',
            '2026-10-09 05:00:00',
        ], $builder->getBindings());
    }
}
