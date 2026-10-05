@extends('layouts.app')

@section('title', 'Pagos sin identificar')
@section('page-heading', 'Pagos sin identificar')

@section('content')
    <div class="mx-auto max-w-[100rem]">
        <div class="mb-6">
            <h2 class="text-2xl font-semibold tracking-tight text-slate-950">Pagos sin identificar</h2>
            <p class="mt-1 text-sm text-slate-600">Pagos cuyo documento efectivo está vacío o aún no ha sido asignado.</p>
        </div>

        @include('payments.partials.filters', [
            'action' => route('payments.unidentified'),
            'filters' => $filters,
            'showDocument' => false,
            'showStatus' => false,
        ])

        <div class="mt-6">
            @include('payments.partials.table', [
                'payments' => $payments,
                'variant' => 'unidentified',
            ])
        </div>
    </div>
@endsection
