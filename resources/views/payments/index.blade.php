@extends('layouts.app')

@section('title', 'Pagos')
@section('page-heading', 'Pagos')

@section('content')
    <div class="kp-page-shell">
        <x-page-header title="Pagos" subtitle="Consulta consolidada de pagos históricos y actuales." />

        @include('payments.partials.filters', [
            'action' => route('payments.index'),
            'filters' => $filters,
        ])

        <div class="mt-3">
            @include('payments.partials.table', ['payments' => $payments])
        </div>
    </div>
@endsection
