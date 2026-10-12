<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\ManagementHistoryReportPeriod;
use Carbon\CarbonImmutable;
use Tests\TestCase;

class ManagementHistoryReportPeriodTest extends TestCase
{
    public function test_uses_calendar_months_and_excludes_the_current_lima_day(): void
    {
        config([
            'reports.management_history.timezone' => 'America/Lima',
            'reports.management_history.source_timezone' => 'UTC',
        ]);
        $period = ManagementHistoryReportPeriod::forExecution(
            CarbonImmutable::parse('2026-10-09 10:30:00', 'America/Lima'),
        );

        $this->assertSame('2025-10-01 00:00:00', $period->startLocal->format('Y-m-d H:i:s'));
        $this->assertSame('2026-10-09 00:00:00', $period->endExclusiveLocal->format('Y-m-d H:i:s'));
        $this->assertSame('2026-10-08', $period->cutoffDateLocal()->format('Y-m-d'));
        $this->assertSame('2025-10-01 05:00:00', $period->startUtc->format('Y-m-d H:i:s'));
        $this->assertSame('2026-10-09 05:00:00', $period->endExclusiveUtc->format('Y-m-d H:i:s'));
        $this->assertSame('20261008', $period->filenameDate());
    }
}
