@props([
    'active' => false,
    'badge' => null,
    'disabled' => false,
    'href' => '#',
])

@php
    $classes = $active
        ? 'border-kp-500 bg-white/8 text-white'
        : 'border-transparent text-slate-300 hover:border-white/20 hover:bg-white/5 hover:text-white';
@endphp

@if ($disabled)
    <span {{ $attributes->merge(['class' => 'flex cursor-not-allowed items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-500']) }}>
        <span class="flex items-center gap-3">
            {{ $icon ?? '' }}
            <span>{{ $slot }}</span>
        </span>
        @if ($badge)
            <span class="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                {{ $badge }}
            </span>
        @endif
    </span>
@else
    <a href="{{ $href }}" {{ $attributes->merge(['class' => 'flex items-center justify-between gap-3 rounded-r-lg border-l-2 px-3 py-2.5 text-sm font-medium transition-colors '.$classes]) }}>
        <span class="flex items-center gap-3">
            {{ $icon ?? '' }}
            <span>{{ $slot }}</span>
        </span>
        @if ($badge)
            <span class="rounded-full bg-kp-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-kp-100">
                {{ $badge }}
            </span>
        @endif
    </a>
@endif
