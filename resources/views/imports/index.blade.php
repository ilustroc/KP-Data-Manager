@extends('layouts.app')

@section('title', 'Historial de cargas')
@section('page-heading', 'Historial de cargas')

@section('content')
    <div class="mx-auto max-w-[96rem]">
        <div class="mb-7 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
                <p class="kp-eyebrow">Operaciones</p>
                <h2 class="mt-2 text-2xl font-semibold tracking-[-0.02em] text-slate-950 sm:text-3xl">Historial de cargas</h2>
                <p class="mt-2 text-sm leading-6 text-slate-600">Consulta los archivos recibidos y el resultado de su procesamiento.</p>
            </div>
            @can('operate')
                <a href="{{ route('imports.create') }}" class="kp-btn-primary">
                    <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14m-7-7h14"/></svg>
                    Nueva carga
                </a>
            @endcan
        </div>

        @include('imports.partials.filters')

        <div class="kp-panel mt-5 overflow-hidden">
            <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3.5 sm:px-5">
                <div>
                    <h3 class="text-sm font-semibold text-slate-950">Cargas registradas</h3>
                    <p class="mt-0.5 text-xs text-slate-500">Ordenadas desde la más reciente.</p>
                </div>
            </div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
                    <thead class="bg-slate-50/80">
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
                    <tbody class="divide-y divide-slate-100 text-slate-700">
                        @forelse ($batches as $batch)
                            <tr class="group transition-colors hover:bg-kp-50/40">
                                <td class="whitespace-nowrap px-4 py-4 align-top">
                                    <a href="{{ route('imports.show', $batch->batch_id) }}" class="font-semibold text-slate-950 group-hover:text-kp-700">Carga #{{ $batch->batch_id }}</a>
                                </td>
                                <td class="max-w-80 px-4 py-4 align-top">
                                    <p class="truncate font-medium text-slate-900" title="{{ $batch->archivo_original ?? $batch->archivo }}">{{ $batch->archivo_original ?? $batch->archivo }}</p>
                                    <p class="mt-1 text-xs text-slate-500"><x-file-size :bytes="$batch->archivo_tamano" /></p>
                                </td>
                                <td class="whitespace-nowrap px-4 py-4 align-top">
                                    <p class="font-medium text-slate-800">
                                        {{ \App\ImportType::tryFrom($batch->tipo)?->label() ?? $batch->tipo }}
                                        @if (filled($batch->entidad))
                                            / {{ \App\FinancialEntity::tryFrom($batch->entidad)?->label() ?? $batch->entidad }}
                                        @endif
                                    </p>
                                    <p class="mt-1 text-xs text-slate-500">{{ \App\ImportOrigin::tryFrom($batch->origen)?->label() ?? $batch->origen }}</p>
                                </td>
                                <td class="whitespace-nowrap px-4 py-4 align-top"><x-import-status-badge :status="$batch->estado" /></td>
                                <td class="whitespace-nowrap px-4 py-4 align-top text-sm text-slate-600"><x-utc-datetime :value="$batch->fecha_inicio" /></td>
                                <td class="whitespace-nowrap px-4 py-4 text-right align-top tabular-nums">
                                    <p class="font-semibold text-slate-900">{{ number_format((int) $batch->filas_insertadas) }} cargadas</p>
                                    <p class="mt-1 text-xs {{ (int) $batch->filas_error > 0 ? 'font-semibold text-red-700' : 'text-slate-500' }}">{{ number_format((int) $batch->filas_error) }} con error</p>
                                </td>
                                <td class="max-w-52 px-4 py-4 align-top text-sm text-slate-700"><span class="line-clamp-2" title="{{ $batch->usuario_nombre }}">{{ $batch->usuario_nombre }}</span></td>
                                <td class="whitespace-nowrap px-4 py-4 text-right align-top">
                                    <a href="{{ route('imports.show', $batch->batch_id) }}" class="inline-flex items-center gap-1 text-sm font-semibold text-kp-700 hover:text-kp-900">Ver detalle <span aria-hidden="true">→</span></a>
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="8" class="px-6 py-16 text-center">
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
