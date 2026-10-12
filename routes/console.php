<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Schedule;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Schedule::command('reports:gestiones-send')
    ->timezone((string) config('reports.management_history.timezone'))
    ->days([1, 2, 3, 4, 5, 6])
    ->at((string) config('reports.management_history.schedule.time', '07:00'))
    ->withoutOverlapping(180)
    ->when(fn (): bool => (bool) config('reports.management_history.schedule.enabled', false));
