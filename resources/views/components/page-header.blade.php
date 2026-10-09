@props([
    'eyebrow' => null,
    'title',
    'subtitle' => null,
])

<header {{ $attributes->class(['kp-page-header']) }}>
    <div class="min-w-0">
        @if ($eyebrow)
            <p class="kp-eyebrow">{{ $eyebrow }}</p>
        @endif
        <h2 class="kp-page-title {{ $eyebrow ? 'mt-1' : '' }}">{{ $title }}</h2>
        @if ($subtitle)
            <p class="kp-page-subtitle">{{ $subtitle }}</p>
        @endif
    </div>
    @isset($actions)
        <div class="flex shrink-0 flex-wrap items-center gap-2">{{ $actions }}</div>
    @endisset
</header>
