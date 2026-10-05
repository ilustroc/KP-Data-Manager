@extends('layouts.app')

@section('title', 'Pagos')
@section('page-heading', 'Pagos')

@section('content')
    <div class="mx-auto max-w-[100rem]">
        <div class="mb-6">
            <h2 class="text-2xl font-semibold tracking-tight text-slate-950">Pagos</h2>
            <p class="mt-1 text-sm text-slate-600">Consulta consolidada de pagos históricos y actuales.</p>
        </div>

        @include('payments.partials.filters', [
            'action' => route('payments.index'),
            'filters' => $filters,
        ])

        <div class="mt-6">
            @include('payments.partials.table', ['payments' => $payments])
        </div>
    </div>
@endsection
