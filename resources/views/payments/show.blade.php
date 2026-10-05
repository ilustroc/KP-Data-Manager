@extends('layouts.app')

@section('title', 'Detalle de pago')
@section('page-heading', 'Detalle de pago')

@section('content')
    <div class="mx-auto max-w-5xl">
        <div class="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
            <div>
                <p class="text-sm font-semibold text-kp-600">Pago #{{ $payment->raw_id }}</p>
                <h2 class="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Información del pago</h2>
                <p class="mt-1 text-sm text-slate-600">Vista de solo lectura del documento efectivo y los datos de origen.</p>
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

        <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <dl class="grid sm:grid-cols-2 lg:grid-cols-3">
                @foreach ([
                    ['label' => 'Raw ID', 'value' => $payment->raw_id, 'mono' => true],
                    ['label' => 'Fecha', 'value' => $payment->FECHA ? \Illuminate\Support\Carbon::parse($payment->FECHA)->format('d/m/Y') : '—'],
                    ['label' => 'Hora', 'value' => $payment->HORA ? substr((string) $payment->HORA, 0, 8) : '—', 'mono' => true],
                    ['label' => 'Documento', 'value' => filled($payment->DOCUMENTO) ? $payment->DOCUMENTO : '—', 'mono' => true],
                    ['label' => 'Monto', 'value' => $payment->MONTO !== null ? 'S/ '.number_format((float) $payment->MONTO, 2, '.', ',') : '—'],
                    ['label' => 'Acumulado', 'value' => $payment->ACUMULADO !== null ? 'S/ '.number_format((float) $payment->ACUMULADO, 2, '.', ',') : '—'],
                    ['label' => 'Recaudo', 'value' => filled($payment->RECAUDO) ? $payment->RECAUDO : '—'],
                    ['label' => 'Operación', 'value' => filled($payment->OPERACION) ? $payment->OPERACION : '—', 'mono' => true],
                    ['label' => 'Archivo de origen', 'value' => filled($payment->source_file) ? $payment->source_file : '—'],
                    ['label' => 'Batch ID', 'value' => filled($payment->batch_id) ? $payment->batch_id : '—', 'mono' => true],
                    ['label' => 'Fecha de ingesta', 'value' => $payment->ingested_at, 'utc_datetime' => true],
                ] as $item)
                    <div class="border-b border-slate-100 px-5 py-4 sm:border-r">
                        <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ $item['label'] }}</dt>
                        <dd @class(['mt-1.5 break-words text-sm text-slate-900', 'font-mono' => $item['mono'] ?? false])>
                            @if ($item['utc_datetime'] ?? false)
                                <x-utc-datetime :value="$item['value']" />
                            @else
                                {{ $item['value'] }}
                            @endif
                        </dd>
                    </div>
                @endforeach
            </dl>

            <div class="px-5 py-5">
                <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">Comentario</p>
                <p class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{{ filled($payment->COMENTARIO) ? $payment->COMENTARIO : '—' }}</p>
            </div>
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
