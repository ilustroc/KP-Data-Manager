@props(['status'])

@php
    $importStatus = \App\ImportStatus::tryFrom((string) $status);
    $classes = match ($importStatus) {
        \App\ImportStatus::Received => ['bg-sky-500', 'border-sky-200 bg-sky-50 text-sky-800'],
        \App\ImportStatus::Validating => ['bg-indigo-500', 'border-indigo-200 bg-indigo-50 text-indigo-800'],
        \App\ImportStatus::Pending => ['bg-amber-500', 'border-amber-200 bg-amber-50 text-amber-900'],
        \App\ImportStatus::Processing => ['bg-blue-500', 'border-blue-200 bg-blue-50 text-blue-800'],
        \App\ImportStatus::Completed => ['bg-emerald-500', 'border-emerald-200 bg-emerald-50 text-emerald-800'],
        \App\ImportStatus::CompletedWithErrors => ['bg-orange-500', 'border-orange-200 bg-orange-50 text-orange-900'],
        \App\ImportStatus::Error => ['bg-red-500', 'border-red-200 bg-red-50 text-red-800'],
        \App\ImportStatus::Cancelled => ['bg-slate-400', 'border-slate-300 bg-slate-100 text-slate-700'],
        default => ['bg-slate-400', 'border-slate-300 bg-slate-50 text-slate-700'],
    };
    $label = $importStatus === \App\ImportStatus::CompletedWithErrors
        ? 'Completado con observaciones'
        : ($importStatus?->label() ?? $status);
@endphp

<span {{ $attributes->class(['inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold', $classes[1]]) }}>
    <span class="size-1.5 rounded-full {{ $classes[0] }}" aria-hidden="true"></span>
    {{ $label }}
</span>
