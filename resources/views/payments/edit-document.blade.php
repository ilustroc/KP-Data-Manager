@extends('layouts.app')

@section('title', 'Corregir documento')
@section('page-heading', 'Corregir documento')

@section('content')
    <div class="kp-page-shell">
        <x-page-header :eyebrow="'Pago #'.$payment->raw_id" title="Corregir documento" subtitle="La asociación vigente será desactivada y el historial permanecerá intacto." />

        @include('payments.partials.document-form', [
            'action' => route('payments.update-document', $payment->raw_id),
            'method' => 'PATCH',
            'mode' => 'correct',
            'payment' => $payment,
        ])
    </div>
@endsection
