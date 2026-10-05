@props([
    'value',
    'format' => 'd/m/Y H:i:s',
    'empty' => '—',
])

@if (filled($value))
    {{ \Illuminate\Support\Carbon::createFromFormat('Y-m-d H:i:s', (string) $value, 'UTC')->setTimezone(config('app.display_timezone'))->format($format) }}
@else
    {{ $empty }}
@endif
