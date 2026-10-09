@extends('layouts.app')

@section('title', 'Dashboard')
@section('page-heading', 'Dashboard operativo')

@section('content')
    <div class="kp-page-shell">
        <x-page-header
            eyebrow="Resumen de la operación"
            :title="$greeting.', '.$firstName"
            subtitle="Consulta el movimiento del día y continúa con las tareas más frecuentes."
        />

        <section class="kp-kpi-strip" aria-label="Indicadores del día">
            @foreach ([
                ['label' => 'Cargas hoy', 'value' => $summary['cargas_hoy'], 'detail' => 'archivos registrados', 'tone' => 'text-ink'],
                ['label' => 'Filas cargadas hoy', 'value' => $summary['filas_cargadas_hoy'], 'detail' => 'registros incorporados', 'tone' => 'text-ink'],
                ['label' => 'Con observaciones', 'value' => $summary['con_observaciones'], 'detail' => 'cargas para revisar', 'tone' => 'text-amber-700'],
                ['label' => 'En proceso', 'value' => $summary['en_proceso'], 'detail' => 'cargas activas hoy', 'tone' => 'text-primary'],
            ] as $indicator)
                <article class="kp-kpi-item">
                    <p class="text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">{{ $indicator['label'] }}</p>
                    <div class="mt-1 flex items-baseline gap-2">
                        <p class="text-2xl font-semibold tabular-nums tracking-[-0.025em] {{ $indicator['tone'] }}">{{ number_format((int) $indicator['value']) }}</p>
                        <p class="text-xs text-muted">{{ $indicator['detail'] }}</p>
                    </div>
                </article>
            @endforeach
        </section>

        <section class="mt-4 flex flex-col gap-2 border-y border-border bg-white px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <h3 class="text-[13px] font-semibold text-ink">Accesos rápidos</h3>
                <p class="text-xs text-muted">Operaciones frecuentes</p>
            </div>
            <div class="flex flex-wrap gap-2">
                @can('operate')
                    <a href="{{ route('imports.create') }}" class="kp-btn-primary">Nueva carga</a>
                @endcan
                <a href="{{ route('payments.index') }}" class="kp-btn-secondary">Ver pagos</a>
                <a href="{{ route('payments.unidentified') }}" class="kp-btn-secondary">Sin identificar</a>
                <a href="{{ route('payments.corrections') }}" class="kp-btn-secondary">Correcciones</a>
            </div>
        </section>

        <section class="kp-panel mt-4 overflow-hidden">
            <div class="kp-section-header">
                <div>
                    <h3 class="text-[13px] font-semibold text-ink">Cargas recientes</h3>
                    <p class="text-[11px] text-muted">Últimos archivos registrados en el sistema</p>
                </div>
                <a href="{{ route('imports.index') }}" class="text-xs font-semibold text-primary hover:text-primary-hover">Ver historial</a>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-border text-left">
                    <thead class="bg-slate-100/80">
                        <tr>
                            <th class="kp-table-heading">Carga</th>
                            <th class="kp-table-heading">Archivo</th>
                            <th class="kp-table-heading">Estado</th>
                            <th class="kp-table-heading">Resultado</th>
                            <th class="kp-table-heading">Fecha</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-border text-slate-700">
                        @forelse ($recentImports as $import)
                            <tr class="hover:bg-blue-50/35">
                                <td class="kp-table-cell whitespace-nowrap"><a href="{{ route('imports.show', $import->batch_id) }}" class="font-semibold text-primary hover:underline">Carga #{{ $import->batch_id }}</a></td>
                                <td class="kp-table-cell max-w-sm"><p class="truncate font-medium text-ink" title="{{ $import->archivo_original ?? $import->archivo }}">{{ $import->archivo_original ?? $import->archivo }}</p></td>
                                <td class="kp-table-cell whitespace-nowrap"><x-import-status-badge :status="$import->estado" /></td>
                                <td class="kp-table-cell whitespace-nowrap">
                                    <span class="font-semibold text-ink">{{ number_format((int) $import->filas_insertadas) }}</span> cargadas
                                    @if ((int) $import->filas_error > 0)
                                        <span class="ml-2 text-xs font-medium text-red-700">{{ number_format((int) $import->filas_error) }} con error</span>
                                    @endif
                                </td>
                                <td class="kp-table-cell whitespace-nowrap text-muted"><x-utc-datetime :value="$import->fecha_inicio" /></td>
                            </tr>
                        @empty
                            <tr><td colspan="5" class="px-6 py-8 text-center text-[13px] text-muted">Todavía no hay cargas registradas.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </section>
    </div>
@endsection
