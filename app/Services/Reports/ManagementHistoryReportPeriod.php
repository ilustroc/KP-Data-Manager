<?php

namespace App\Services\Reports;

use Carbon\CarbonImmutable;
use DateTimeInterface;

class ManagementHistoryReportPeriod
{
    public function __construct(
        public readonly CarbonImmutable $generatedAtLocal,
        public readonly CarbonImmutable $startLocal,
        public readonly CarbonImmutable $endExclusiveLocal,
        public readonly CarbonImmutable $startUtc,
        public readonly CarbonImmutable $endExclusiveUtc,
    ) {}

    public static function forExecution(DateTimeInterface $executedAt): self
    {
        $localTimezone = (string) config('reports.management_history.timezone', 'America/Lima');
        $sourceTimezone = (string) config('reports.management_history.source_timezone', 'UTC');
        $generatedAtLocal = CarbonImmutable::instance($executedAt)->setTimezone($localTimezone);
        $startLocal = $generatedAtLocal->startOfMonth()->subMonths(12);
        $endExclusiveLocal = $generatedAtLocal->startOfDay();

        return new self(
            generatedAtLocal: $generatedAtLocal,
            startLocal: $startLocal,
            endExclusiveLocal: $endExclusiveLocal,
            startUtc: $startLocal->setTimezone($sourceTimezone),
            endExclusiveUtc: $endExclusiveLocal->setTimezone($sourceTimezone),
        );
    }

    public function cutoffDateLocal(): CarbonImmutable
    {
        return $this->endExclusiveLocal->subDay();
    }

    public function filenameDate(): string
    {
        return $this->cutoffDateLocal()->format('Ymd');
    }

    public function displayStart(): string
    {
        return $this->startLocal->format('d/m/Y');
    }

    public function displayEnd(): string
    {
        return $this->cutoffDateLocal()->format('d/m/Y');
    }
}
