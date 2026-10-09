@extends('layouts.app')

@section('title', 'Identificar pago')
@section('page-heading', 'Identificar pago')

@section('content')
    <div class="kp-page-shell">
        <x-page-header :eyebrow="'Pago #'.$payment->raw_id" title="Identificar pago" subtitle="Asocia un documento al pago y conserva el historial del cambio." />

        @include('payments.partials.document-form', [
            'action' => route('payments.identify', $payment->raw_id),
            'method' => 'POST',
            'mode' => 'identify',
            'payment' => $payment,
        ])
    </div>
@endsection
