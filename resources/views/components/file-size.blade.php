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
    $formattedSize = number_format($displaySize, $decimals, '.', ',');
    if ($decimals > 0) {
        $formattedSize = rtrim(rtrim($formattedSize, '0'), '.');
    }
@endphp

{{ $size === null ? '—' : $formattedSize.' '.$units[$unitIndex] }}
