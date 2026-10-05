@props(['status'])

@php
    $importStatus = \App\ImportStatus::tryFrom((string) $status);
    $classes = match ($importStatus) {
        \App\ImportStatus::Received => 'border-sky-200 bg-sky-50 text-sky-700',
        \App\ImportStatus::Validating => 'border-indigo-200 bg-indigo-50 text-indigo-700',
        \App\ImportStatus::Pending => 'border-amber-200 bg-amber-50 text-amber-800',
        \App\ImportStatus::Processing => 'border-blue-200 bg-blue-50 text-blue-700',
        \App\ImportStatus::Completed => 'border-emerald-200 bg-emerald-50 text-emerald-700',
        \App\ImportStatus::CompletedWithErrors => 'border-orange-200 bg-orange-50 text-orange-800',
        \App\ImportStatus::Error => 'border-red-200 bg-red-50 text-red-700',
        \App\ImportStatus::Cancelled => 'border-slate-300 bg-slate-100 text-slate-700',
        default => 'border-slate-300 bg-slate-50 text-slate-700',
    };
@endphp

<span {{ $attributes->class(['inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold', $classes]) }}>
    {{ $importStatus?->label() ?? $status }}
</span>
