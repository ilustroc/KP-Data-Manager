@extends('layouts.app')

@section('title', 'Corregir documento')
@section('page-heading', 'Corregir documento')

@section('content')
    <div class="mx-auto max-w-6xl">
        <div class="mb-6">
            <p class="text-sm font-semibold text-kp-600">Pago #{{ $payment->raw_id }}</p>
            <h2 class="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Corregir documento</h2>
            <p class="mt-1 text-sm text-slate-600">La asociación vigente será desactivada y el historial permanecerá intacto.</p>
        </div>

        @include('payments.partials.document-form', [
            'action' => route('payments.update-document', $payment->raw_id),
            'method' => 'PATCH',
            'mode' => 'correct',
            'payment' => $payment,
        ])
    </div>
@endsection
