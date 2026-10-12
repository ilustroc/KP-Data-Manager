<?php

namespace Tests\Feature\Console;

use App\Console\Commands\SendManagementHistoryReport;
use Cron\CronExpression;
use Illuminate\Console\Scheduling\Event;
use Illuminate\Console\Scheduling\Schedule;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Support\Facades\Artisan;
use Tests\TestCase;

class ManagementHistoryReportScheduleTest extends TestCase
{
    public function test_report_is_scheduled_monday_through_saturday_at_seven_in_lima_without_overlap(): void
    {
        config(['reports.management_history.schedule.enabled' => true]);

        $event = $this->managementHistoryReportEvent();

        $this->assertTrue($event->filtersPass($this->app));
        $this->assertSame('0 7 * * 1,2,3,4,5,6', $event->expression);
        $this->assertSame('America/Lima', $event->timezone);
        $this->assertTrue($event->withoutOverlapping);
        $this->assertSame(180, $event->expiresAt);
        $this->assertFalse($event->onOneServer);
        $this->assertFalse($event->runInBackground);

        $cron = new CronExpression($event->expression);
        $this->assertTrue($cron->isDue('2026-10-05T07:00:00-05:00', 'America/Lima'));
        $this->assertTrue($cron->isDue('2026-10-06T07:00:00-05:00', 'America/Lima'));
        $this->assertTrue($cron->isDue('2026-10-07T07:00:00-05:00', 'America/Lima'));
        $this->assertTrue($cron->isDue('2026-10-08T07:00:00-05:00', 'America/Lima'));
        $this->assertTrue($cron->isDue('2026-10-09T07:00:00-05:00', 'America/Lima'));
        $this->assertTrue($cron->isDue('2026-10-10T07:00:00-05:00', 'America/Lima'));
        $this->assertFalse($cron->isDue('2026-10-11T07:00:00-05:00', 'America/Lima'));
    }

    public function test_disabled_schedule_does_not_pass_execution_filters(): void
    {
        config(['reports.management_history.schedule.enabled' => false]);

        $event = $this->managementHistoryReportEvent();

        $this->assertFalse($event->filtersPass($this->app));
    }

    public function test_manual_command_remains_available_without_a_queued_job(): void
    {
        $commands = Artisan::all();

        $this->assertArrayHasKey('reports:gestiones-send', $commands);
        $this->assertInstanceOf(SendManagementHistoryReport::class, $commands['reports:gestiones-send']);
        $this->assertFalse(is_subclass_of(SendManagementHistoryReport::class, ShouldQueue::class));
    }

    private function managementHistoryReportEvent(): Event
    {
        $events = array_values(array_filter(
            $this->app->make(Schedule::class)->events(),
            fn (Event $event): bool => str_contains((string) $event->command, 'reports:gestiones-send'),
        ));

        $this->assertCount(1, $events);

        return $events[0];
    }
}
