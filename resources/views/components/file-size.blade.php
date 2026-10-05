@props(['bytes'])

@php
    $size = $bytes === null ? null : max(0, (int) $bytes);
    $units = ['B', 'KB', 'MB', 'GB', 'TB'];
    $unitIndex = 0;
    $displaySize = (float) ($size ?? 0);

    while ($displaySize >= 1024 && $unitIndex < count($units) - 1) {
        $displaySize /= 1024;
        $unitIndex++;
    }

    $decimals = $unitIndex === 0 ? 0 : 2;
@endphp

{{ $size === null ? '—' : number_format($displaySize, $decimals, '.', ',').' '.$units[$unitIndex] }}
