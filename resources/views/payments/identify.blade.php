@extends('layouts.app')

@section('title', 'Identificar pago')
@section('page-heading', 'Identificar pago')

@section('content')
    <div class="mx-auto max-w-6xl">
        <div class="mb-6">
            <p class="text-sm font-semibold text-kp-600">Pago #{{ $payment->raw_id }}</p>
            <h2 class="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Identificar pago</h2>
            <p class="mt-1 text-sm text-slate-600">Asocia un documento al pago y conserva el historial del cambio.</p>
        </div>

        @include('payments.partials.document-form', [
            'action' => route('payments.identify', $payment->raw_id),
            'method' => 'POST',
            'mode' => 'identify',
            'payment' => $payment,
        ])
    </div>
@endsection
