@extends('layouts.app')

@section('title', 'Historial de cargas')
@section('page-heading', 'Historial de cargas')

@section('content')
    <div class="kp-page-shell">
        <x-page-header title="Historial de cargas" subtitle="Consulta los archivos recibidos y el resultado de su procesamiento.">
            <x-slot:actions>
                @can('operate')
                    <a href="{{ route('imports.create') }}" class="kp-btn-primary">
                        <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14m-7-7h14"/></svg>
                        Nueva carga
                    </a>
                @endcan
            </x-slot:actions>
        </x-page-header>

        @include('imports.partials.filters')

        <div class="kp-panel mt-3 overflow-hidden">
            <div class="kp-section-header">
                <div>
                    <h3 class="text-sm font-semibold text-slate-950">Cargas registradas</h3>
                    <p class="text-[11px] text-muted">Ordenadas desde la más reciente</p>
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-border text-left">
                    <thead class="bg-slate-100/80">
                        <tr>
                            <th class="kp-table-heading">Carga</th>
                            <th class="kp-table-heading">Archivo</th>
                            <th class="kp-table-heading">Tipo / origen</th>
                            <th class="kp-table-heading">Estado</th>
                            <th class="kp-table-heading">Registro</th>
                            <th class="kp-table-heading text-right">Resultado</th>
                            <th class="kp-table-heading">Usuario</th>
                            <th class="kp-table-heading"><span class="sr-only">Acciones</span></th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-border text-slate-700">
                        @forelse ($batches as $batch)
                            <tr class="group hover:bg-blue-50/35">
                                <td class="kp-table-cell whitespace-nowrap align-top">
                                    <a href="{{ route('imports.show', $batch->batch_id) }}" class="font-semibold text-primary hover:underline">Carga #{{ $batch->batch_id }}</a>
                                </td>
                                <td class="kp-table-cell max-w-80 align-top">
                                    <p class="truncate font-medium text-ink" title="{{ $batch->archivo_original ?? $batch->archivo }}">{{ $batch->archivo_original ?? $batch->archivo }}</p>
                                    <p class="text-[11px] text-muted"><x-file-size :bytes="$batch->archivo_tamano" /></p>
                                </td>
                                <td class="kp-table-cell whitespace-nowrap align-top">
                                    <p class="font-medium text-ink">
                                        {{ \App\ImportType::tryFrom($batch->tipo)?->label() ?? $batch->tipo }}
                                        @if (filled($batch->entidad))
                                            / {{ \App\FinancialEntity::tryFrom($batch->entidad)?->label() ?? $batch->entidad }}
                                        @endif
                                        @if (filled($batch->dataset_code))
                                            / {{ $batch->dataset_code }} · {{ $batch->source_code }}
                                        @endif
                                    </p>
                                    <p class="text-[11px] text-muted">{{ \App\ImportOrigin::tryFrom($batch->origen)?->label() ?? $batch->origen }}</p>
                                </td>
                                <td class="kp-table-cell whitespace-nowrap align-top"><x-import-status-badge :status="$batch->estado" /></td>
                                <td class="kp-table-cell whitespace-nowrap align-top text-muted"><x-utc-datetime :value="$batch->fecha_inicio" /></td>
                                <td class="kp-table-cell whitespace-nowrap text-right align-top tabular-nums">
                                    <p class="font-semibold text-ink">{{ number_format((int) $batch->filas_insertadas) }} cargadas</p>
                                    <p class="text-[11px] {{ (int) $batch->filas_error > 0 ? 'font-semibold text-red-700' : 'text-muted' }}">{{ number_format((int) $batch->filas_error) }} con error</p>
                                </td>
                                <td class="kp-table-cell max-w-52 align-top"><span class="line-clamp-2" title="{{ $batch->usuario_nombre }}">{{ $batch->usuario_nombre }}</span></td>
                                <td class="kp-table-cell whitespace-nowrap text-right align-top">
                                    <a href="{{ route('imports.show', $batch->batch_id) }}" class="text-xs font-semibold text-primary hover:underline">Ver detalle</a>
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="8" class="px-6 py-8 text-center">
                                    <div class="mx-auto grid size-11 place-items-center rounded-full bg-slate-100 text-slate-400">
                                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 7h16M4 12h16M4 17h10"/></svg>
                                    </div>
                                    <p class="mt-3 text-sm font-semibold text-slate-700">No se encontraron cargas</p>
                                    <p class="mt-1 text-sm text-slate-500">Prueba con otros criterios de búsqueda.</p>
                                </td>
                            </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>

            @if ($batches->hasPages())
                <div class="border-t border-slate-200 px-4 py-3">{{ $batches->links() }}</div>
            @endif
        </div>
    </div>
@endsection
