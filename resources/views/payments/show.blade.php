@extends('layouts.app')

@section('title', 'Detalle de pago')
@section('page-heading', 'Detalle de pago')

@section('content')
    <div class="mx-auto max-w-5xl">
        <div class="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
            <div>
                <p class="text-sm font-semibold text-kp-600">Pago #{{ $payment->raw_id }}</p>
                <h2 class="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Información del pago</h2>
                <p class="mt-1 text-sm text-slate-600">Consulta el documento vigente y la información registrada del pago.</p>
            </div>
            <div class="flex flex-wrap gap-2">
                @can('operate')
                    @if (blank($payment->DOCUMENTO))
                        <a href="{{ route('payments.identify.create', $payment->raw_id) }}" class="inline-flex rounded-lg bg-kp-600 px-4 py-2 text-sm font-semibold text-white hover:bg-kp-700">Identificar</a>
                    @else
                        <a href="{{ route('payments.edit-document', $payment->raw_id) }}" class="inline-flex rounded-lg bg-kp-600 px-4 py-2 text-sm font-semibold text-white hover:bg-kp-700">Corregir documento</a>
                    @endif
                @endcan
                <a href="{{ route('payments.index') }}" class="inline-flex rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Volver a pagos</a>
            </div>
        </div>

        <section class="kp-panel overflow-hidden">
            <dl class="grid sm:grid-cols-3">
                <div class="border-b border-slate-100 px-5 py-4 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Documento</dt>
                    <dd class="mt-1.5 font-mono text-base font-semibold text-slate-950">{{ filled($payment->DOCUMENTO) ? $payment->DOCUMENTO : 'Sin identificar' }}</dd>
                </div>
                <div class="border-b border-slate-100 px-5 py-4 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Fecha</dt>
                    <dd class="mt-1.5 text-sm text-slate-900">{{ $payment->FECHA ? \Illuminate\Support\Carbon::parse($payment->FECHA)->format('d/m/Y') : '—' }}</dd>
                </div>
                <div class="border-b border-slate-100 px-5 py-4">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Hora</dt>
                    <dd class="mt-1.5 font-mono text-sm text-slate-900">{{ $payment->HORA ? substr((string) $payment->HORA, 0, 8) : '—' }}</dd>
                </div>
                <div class="border-b border-slate-100 px-5 py-4 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Monto</dt>
                    <dd class="mt-1.5 text-base font-semibold text-slate-950">{{ $payment->MONTO !== null ? 'S/ '.number_format((float) $payment->MONTO, 2, '.', ',') : '—' }}</dd>
                </div>
                <div class="border-b border-slate-100 px-5 py-4 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Acumulado</dt>
                    <dd class="mt-1.5 text-sm font-medium text-slate-900">{{ $payment->ACUMULADO !== null ? 'S/ '.number_format((float) $payment->ACUMULADO, 2, '.', ',') : '—' }}</dd>
                </div>
                <div class="border-b border-slate-100 px-5 py-4">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Recaudo</dt>
                    <dd class="mt-1.5 text-sm font-medium text-slate-900">{{ filled($payment->RECAUDO) ? $payment->RECAUDO : '—' }}</dd>
                </div>
                <div class="border-b border-slate-100 px-5 py-4 sm:col-span-3">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Operación</dt>
                    <dd class="mt-1.5 font-mono text-sm text-slate-900">{{ filled($payment->OPERACION) ? $payment->OPERACION : '—' }}</dd>
                </div>
                <div class="px-5 py-5 sm:col-span-3">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">Comentario</dt>
                    <dd class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{{ filled($payment->COMENTARIO) ? $payment->COMENTARIO : 'Sin comentario' }}</dd>
                </div>
            </dl>
        </section>

        <section class="mt-6">
            <div class="mb-3 flex items-center justify-between gap-4">
                <div>
                    <h3 class="font-semibold text-slate-900">Historial de asociaciones</h3>
                    <p class="mt-1 text-sm text-slate-500">Cada cambio queda conservado permanentemente.</p>
                </div>
                <a href="{{ route('payments.history', $payment->raw_id) }}" class="text-sm font-semibold text-kp-600 hover:text-kp-700">Ver historial completo</a>
            </div>
            @include('payments.partials.history-table', ['history' => $history])
        </section>
    </div>
@endsection
