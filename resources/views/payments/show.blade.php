@extends('layouts.app')

@section('title', 'Detalle de pago')
@section('page-heading', 'Detalle de pago')

@section('content')
    <div class="kp-page-shell">
        <x-page-header :eyebrow="'Pago #'.$payment->raw_id" title="Información del pago" subtitle="Consulta el documento vigente y la información registrada del pago.">
            <x-slot:actions>
                @can('operate')
                    @if (blank($payment->DOCUMENTO))
                        <a href="{{ route('payments.identify.create', $payment->raw_id) }}" class="kp-btn-primary">Identificar</a>
                    @else
                        <a href="{{ route('payments.edit-document', $payment->raw_id) }}" class="kp-btn-primary">Corregir documento</a>
                    @endif
                @endcan
                <a href="{{ route('payments.index') }}" class="kp-btn-secondary">Volver a pagos</a>
            </x-slot:actions>
        </x-page-header>

        <section class="kp-panel overflow-hidden">
            <dl class="grid sm:grid-cols-3">
                <div class="border-b border-border px-4 py-3 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Documento</dt>
                    <dd class="mt-1.5 font-mono text-base font-semibold text-slate-950">{{ filled($payment->DOCUMENTO) ? $payment->DOCUMENTO : 'Sin identificar' }}</dd>
                </div>
                <div class="border-b border-border px-4 py-3 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Fecha</dt>
                    <dd class="mt-1.5 text-sm text-slate-900">{{ $payment->FECHA ? \Illuminate\Support\Carbon::parse($payment->FECHA)->format('d/m/Y') : '—' }}</dd>
                </div>
                <div class="border-b border-border px-4 py-3">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Hora</dt>
                    <dd class="mt-1.5 font-mono text-sm text-slate-900">{{ $payment->HORA ? substr((string) $payment->HORA, 0, 8) : '—' }}</dd>
                </div>
                <div class="border-b border-border px-4 py-3 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Monto</dt>
                    <dd class="mt-1.5 text-base font-semibold text-slate-950">{{ $payment->MONTO !== null ? 'S/ '.number_format((float) $payment->MONTO, 2, '.', ',') : '—' }}</dd>
                </div>
                <div class="border-b border-border px-4 py-3 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Acumulado</dt>
                    <dd class="mt-1.5 text-sm font-medium text-slate-900">{{ $payment->ACUMULADO !== null ? 'S/ '.number_format((float) $payment->ACUMULADO, 2, '.', ',') : '—' }}</dd>
                </div>
                <div class="border-b border-border px-4 py-3">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Recaudo</dt>
                    <dd class="mt-1.5 text-sm font-medium text-slate-900">{{ filled($payment->RECAUDO) ? $payment->RECAUDO : '—' }}</dd>
                </div>
                <div class="border-b border-border px-4 py-3 sm:col-span-3">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Operación</dt>
                    <dd class="mt-1.5 font-mono text-sm text-slate-900">{{ filled($payment->OPERACION) ? $payment->OPERACION : '—' }}</dd>
                </div>
                <div class="px-4 py-3 sm:col-span-3">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Comentario</dt>
                    <dd class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{{ filled($payment->COMENTARIO) ? $payment->COMENTARIO : 'Sin comentario' }}</dd>
                </div>
            </dl>
        </section>

        <section class="mt-4">
            <div class="mb-3 flex items-center justify-between gap-4">
                <div>
                    <h3 class="font-semibold text-slate-900">Historial de asociaciones</h3>
                    <p class="mt-1 text-sm text-slate-500">Cada cambio queda conservado permanentemente.</p>
                </div>
                <a href="{{ route('payments.history', $payment->raw_id) }}" class="text-xs font-semibold text-primary hover:underline">Ver historial completo</a>
            </div>
            @include('payments.partials.history-table', ['history' => $history])
        </section>
    </div>
@endsection
