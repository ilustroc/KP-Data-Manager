@extends('layouts.app')

@section('title', 'Historial de asociaciones')
@section('page-heading', 'Historial de asociaciones')

@section('content')
    <div class="mx-auto max-w-[100rem]">
        <div class="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
            <div>
                <p class="text-sm font-semibold text-kp-600">Pago #{{ $payment->raw_id }}</p>
                <h2 class="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Historial de asociaciones</h2>
                <p class="mt-1 text-sm text-slate-600">Documento efectivo: <span class="font-mono font-semibold text-slate-900">{{ filled($payment->DOCUMENTO) ? $payment->DOCUMENTO : 'Sin identificar' }}</span></p>
            </div>
            <a href="{{ route('payments.show', $payment->raw_id) }}" class="inline-flex w-fit rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Volver al pago</a>
        </div>

        @include('payments.partials.history-table', ['history' => $history])
    </div>
@endsection
