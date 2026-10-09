@extends('layouts.app')

@section('title', 'Pagos sin identificar')
@section('page-heading', 'Pagos sin identificar')

@section('content')
    <div class="kp-page-shell">
        <x-page-header title="Pagos sin identificar" subtitle="Pagos cuyo documento efectivo está vacío o aún no ha sido asignado." />

        @include('payments.partials.filters', [
            'action' => route('payments.unidentified'),
            'filters' => $filters,
            'showDocument' => false,
            'showStatus' => false,
        ])

        <div class="mt-3">
            @include('payments.partials.table', [
                'payments' => $payments,
                'variant' => 'unidentified',
            ])
        </div>
    </div>
@endsection
