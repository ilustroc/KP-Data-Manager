@extends('layouts.app')

@section('title', 'Historial de cargas')
@section('page-heading', 'Historial de cargas')

@section('content')
    <div class="mx-auto max-w-[100rem]">
        <div class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
                <h2 class="text-2xl font-semibold tracking-tight text-slate-950">Cargas</h2>
                <p class="mt-1 text-sm text-slate-600">Archivos recibidos y estado de sus procesos de importación.</p>
            </div>
            @can('operate')
                <a href="{{ route('imports.create') }}" class="inline-flex items-center justify-center rounded-lg bg-kp-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-kp-700">Nueva carga</a>
            @endcan
        </div>

        @include('imports.partials.filters')

        <div class="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
                    <thead class="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <tr>
                            <th class="px-4 py-3">Batch</th>
                            <th class="px-4 py-3">Tipo</th>
                            <th class="px-4 py-3">Origen</th>
                            <th class="px-4 py-3">Archivo</th>
                            <th class="px-4 py-3 text-right">Tamaño</th>
                            <th class="px-4 py-3">Estado</th>
                            <th class="px-4 py-3">Fecha registro</th>
                            <th class="px-4 py-3">Usuario</th>
                            <th class="px-4 py-3 text-right">Filas</th>
                            <th class="px-4 py-3 text-right">Errores</th>
                            <th class="px-4 py-3">Acción</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100 text-slate-700">
                        @forelse ($batches as $batch)
                            <tr class="hover:bg-slate-50/70">
                                <td class="whitespace-nowrap px-4 py-3 font-mono font-semibold text-slate-900">#{{ $batch->batch_id }}</td>
                                <td class="whitespace-nowrap px-4 py-3">{{ \App\ImportType::tryFrom($batch->tipo)?->label() ?? $batch->tipo }}</td>
                                <td class="whitespace-nowrap px-4 py-3">{{ \App\ImportOrigin::tryFrom($batch->origen)?->label() ?? $batch->origen }}</td>
                                <td class="max-w-72 truncate px-4 py-3" title="{{ $batch->archivo_original ?? $batch->archivo }}">{{ $batch->archivo_original ?? $batch->archivo }}</td>
                                <td class="whitespace-nowrap px-4 py-3 text-right tabular-nums"><x-file-size :bytes="$batch->archivo_tamano" /></td>
                                <td class="whitespace-nowrap px-4 py-3"><x-import-status-badge :status="$batch->estado" /></td>
                                <td class="whitespace-nowrap px-4 py-3"><x-utc-datetime :value="$batch->fecha_inicio" /></td>
                                <td class="whitespace-nowrap px-4 py-3 font-mono text-xs">{{ $batch->usuario ?: '—' }}</td>
                                <td class="whitespace-nowrap px-4 py-3 text-right tabular-nums">{{ number_format((int) $batch->filas_archivo) }}</td>
                                <td class="whitespace-nowrap px-4 py-3 text-right tabular-nums">{{ number_format((int) $batch->filas_error) }}</td>
                                <td class="whitespace-nowrap px-4 py-3"><a href="{{ route('imports.show', $batch->batch_id) }}" class="font-semibold text-kp-600 hover:text-kp-700">Ver</a></td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="11" class="px-6 py-14 text-center text-sm text-slate-500">No se encontraron cargas con los filtros seleccionados.</td>
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
