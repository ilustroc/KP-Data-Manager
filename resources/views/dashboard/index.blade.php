@extends('layouts.app')

@section('title', 'Dashboard')
@section('page-heading', 'Dashboard')

@section('content')
    <div class="mx-auto max-w-[96rem]">
        <header class="mb-7">
            <p class="kp-eyebrow">Resumen de la operación</p>
            <h2 class="mt-2 text-2xl font-semibold tracking-[-0.02em] text-slate-950 sm:text-3xl">{{ $greeting }}, {{ $firstName }}</h2>
            <p class="mt-2 text-sm text-slate-600">Consulta el movimiento del día y continúa con las tareas más frecuentes.</p>
        </header>

        <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Indicadores del día">
            @foreach ([
                ['label' => 'Cargas hoy', 'value' => $summary['cargas_hoy'], 'detail' => 'archivos registrados', 'icon' => 'upload'],
                ['label' => 'Filas cargadas hoy', 'value' => $summary['filas_cargadas_hoy'], 'detail' => 'registros incorporados', 'icon' => 'rows'],
                ['label' => 'Con observaciones', 'value' => $summary['con_observaciones'], 'detail' => 'cargas para revisar', 'icon' => 'warning'],
                ['label' => 'En proceso', 'value' => $summary['en_proceso'], 'detail' => 'cargas activas hoy', 'icon' => 'progress'],
            ] as $indicator)
                <article class="kp-panel flex items-start justify-between gap-4 p-5">
                    <div>
                        <p class="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">{{ $indicator['label'] }}</p>
                        <p class="mt-2 text-3xl font-semibold tabular-nums tracking-[-0.03em] text-slate-950">{{ number_format((int) $indicator['value']) }}</p>
                        <p class="mt-1 text-xs text-slate-500">{{ $indicator['detail'] }}</p>
                    </div>
                    <div @class([
                        'grid size-10 shrink-0 place-items-center rounded-lg',
                        'bg-kp-50 text-kp-700' => $indicator['icon'] !== 'warning',
                        'bg-orange-50 text-orange-700' => $indicator['icon'] === 'warning',
                    ])>
                        @if ($indicator['icon'] === 'upload')
                            <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4"/></svg>
                        @elseif ($indicator['icon'] === 'rows')
                            <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 7h16M4 12h16M4 17h10"/></svg>
                        @elseif ($indicator['icon'] === 'warning')
                            <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8v5m0 3h.01M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/></svg>
                        @else
                            <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M20 12a8 8 0 1 1-2.34-5.66M20 4v6h-6"/></svg>
                        @endif
                    </div>
                </article>
            @endforeach
        </section>

        <section class="mt-5 rounded-xl border border-slate-200 bg-white px-4 py-3.5 sm:flex sm:items-center sm:justify-between sm:px-5">
            <div>
                <h3 class="text-sm font-semibold text-slate-950">Accesos rápidos</h3>
                <p class="mt-0.5 text-xs text-slate-500">Continúa con una tarea frecuente.</p>
            </div>
            <div class="mt-3 flex flex-wrap gap-2 sm:mt-0">
                @can('operate')
                    <a href="{{ route('imports.create') }}" class="kp-btn-primary !px-3.5 !py-2">Nueva carga</a>
                @endcan
                <a href="{{ route('payments.index') }}" class="kp-btn-secondary !px-3.5 !py-2">Ver pagos</a>
                <a href="{{ route('payments.unidentified') }}" class="kp-btn-secondary !px-3.5 !py-2">Sin identificar</a>
                <a href="{{ route('payments.corrections') }}" class="kp-btn-secondary !px-3.5 !py-2">Correcciones</a>
            </div>
        </section>

        <section class="kp-panel mt-5 overflow-hidden">
            <div class="flex items-center justify-between gap-4 border-b border-slate-200 px-4 py-4 sm:px-5">
                <div>
                    <h3 class="text-sm font-semibold text-slate-950">Cargas recientes</h3>
                    <p class="mt-0.5 text-xs text-slate-500">Últimos archivos registrados en el sistema.</p>
                </div>
                <a href="{{ route('imports.index') }}" class="text-sm font-semibold text-kp-700 hover:text-kp-900">Ver historial</a>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
                    <thead class="bg-slate-50/80">
                        <tr>
                            <th class="kp-table-heading">Carga</th>
                            <th class="kp-table-heading">Archivo</th>
                            <th class="kp-table-heading">Estado</th>
                            <th class="kp-table-heading">Resultado</th>
                            <th class="kp-table-heading">Fecha</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100 text-slate-700">
                        @forelse ($recentImports as $import)
                            <tr class="hover:bg-kp-50/30">
                                <td class="whitespace-nowrap px-4 py-3.5"><a href="{{ route('imports.show', $import->batch_id) }}" class="font-semibold text-slate-950 hover:text-kp-700">Carga #{{ $import->batch_id }}</a></td>
                                <td class="max-w-sm px-4 py-3.5"><p class="truncate font-medium text-slate-800" title="{{ $import->archivo_original ?? $import->archivo }}">{{ $import->archivo_original ?? $import->archivo }}</p></td>
                                <td class="whitespace-nowrap px-4 py-3.5"><x-import-status-badge :status="$import->estado" /></td>
                                <td class="whitespace-nowrap px-4 py-3.5">
                                    <p class="font-semibold text-slate-900">{{ number_format((int) $import->filas_insertadas) }} cargadas</p>
                                    @if ((int) $import->filas_error > 0)
                                        <p class="mt-0.5 text-xs font-medium text-red-700">{{ number_format((int) $import->filas_error) }} con error</p>
                                    @endif
                                </td>
                                <td class="whitespace-nowrap px-4 py-3.5 text-slate-600"><x-utc-datetime :value="$import->fecha_inicio" /></td>
                            </tr>
                        @empty
                            <tr><td colspan="5" class="px-6 py-12 text-center text-sm text-slate-500">Todavía no hay cargas registradas.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </section>
    </div>
@endsection
