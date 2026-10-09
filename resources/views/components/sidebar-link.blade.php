@props([
    'active' => false,
    'badge' => null,
    'disabled' => false,
    'href' => '#',
])

@php
    $classes = $active
        ? 'border-primary bg-blue-50 text-primary'
        : 'border-transparent text-slate-600 hover:bg-slate-100 hover:text-topbar';
@endphp

@if ($disabled)
    <span {{ $attributes->merge(['class' => 'group relative flex h-10 cursor-not-allowed items-center gap-3 border-l-2 px-3 text-slate-400 lg:justify-center lg:px-0']) }} title="{{ trim($slot) }}">
        <span class="shrink-0">{{ $icon ?? '' }}</span>
        <span class="text-[13px] lg:sr-only">{{ $slot }}</span>
    </span>
@else
    <a href="{{ $href }}" title="{{ trim($slot) }}" @if ($active) aria-current="page" @endif {{ $attributes->merge(['class' => 'group relative flex h-10 items-center gap-3 border-l-2 px-3 text-[13px] font-medium transition-colors lg:justify-center lg:px-0 '.$classes]) }}>
        <span class="shrink-0">{{ $icon ?? '' }}</span>
        <span class="lg:sr-only">{{ $slot }}</span>
        <span class="pointer-events-none absolute left-full z-50 ml-2 hidden whitespace-nowrap rounded-control bg-slate-950 px-2 py-1.5 text-xs font-medium text-white shadow-lg lg:group-hover:block lg:group-focus-visible:block" role="tooltip">{{ $slot }}</span>
        @if ($badge)
            <span class="ml-auto rounded-control bg-slate-200 px-1.5 py-0.5 text-[10px] lg:absolute lg:top-1 lg:right-1">{{ $badge }}</span>
        @endif
    </a>
@endif
