@extends('layouts.app')

@section('title', 'Historial de asociaciones')
@section('page-heading', 'Historial de asociaciones')

@section('content')
    <div class="kp-page-shell">
        <x-page-header :eyebrow="'Pago #'.$payment->raw_id" title="Historial de asociaciones" :subtitle="'Documento efectivo: '.(filled($payment->DOCUMENTO) ? $payment->DOCUMENTO : 'Sin identificar')">
            <x-slot:actions><a href="{{ route('payments.show', $payment->raw_id) }}" class="kp-btn-secondary">Volver al pago</a></x-slot:actions>
        </x-page-header>

        @include('payments.partials.history-table', ['history' => $history])
    </div>
@endsection
