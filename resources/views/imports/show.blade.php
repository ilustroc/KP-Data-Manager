@extends('layouts.app')

@section('title', 'Carga #'.$batch->batch_id)
@section('page-heading', 'Detalle de carga')

@php
    $importStatus = \App\ImportStatus::tryFrom((string) $batch->estado);
    $refreshesAutomatically = in_array($importStatus, [\App\ImportStatus::Pending, \App\ImportStatus::Processing], true);
@endphp

@section('content')
    <div class="mx-auto max-w-6xl" @if ($refreshesAutomatically) data-auto-refresh-url="{{ route('imports.show', $batch->batch_id) }}" data-auto-refresh-after="8000" @endif>
        <a href="{{ route('imports.index') }}" class="mb-5 inline-flex items-center gap-1.5 text-sm font-semibold text-slate-500 hover:text-kp-700">
            <span aria-hidden="true">←</span>
            Volver a cargas
        </a>

        <div class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0">
                <p class="kp-eyebrow">Registro de procesamiento</p>
                <div class="mt-2 flex flex-wrap items-center gap-3">
                    <h2 class="text-2xl font-semibold tracking-[-0.02em] text-slate-950 sm:text-3xl">Carga #{{ $batch->batch_id }}</h2>
                    <x-import-status-badge :status="$batch->estado" />
                </div>
                <p class="mt-2 break-all text-sm text-slate-600">{{ $batch->archivo_original ?? $batch->archivo }}</p>
            </div>
        </div>

        @if ($importStatus === \App\ImportStatus::Pending)
            <section class="kp-panel mb-5 flex flex-col gap-4 border-l-4 border-l-amber-500 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-start gap-3">
                    <div class="grid size-10 shrink-0 place-items-center rounded-full bg-amber-100 text-amber-700">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke-width="1.8"/><path stroke-linecap="round" stroke-width="1.8" d="M12 7v5l3 2"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">Preparando procesamiento...</h3>
                        <p class="mt-1 text-sm text-slate-600">Carga registrada y enviada a procesamiento.</p>
                        <p class="mt-2 text-xs text-slate-500">El estado se actualiza automáticamente.</p>
                    </div>
                </div>
                <a href="{{ route('imports.show', $batch->batch_id) }}" class="kp-btn-secondary whitespace-nowrap">Actualizar estado</a>
            </section>
        @elseif ($importStatus === \App\ImportStatus::Processing)
            <section class="kp-panel mb-5 flex flex-col gap-4 border-l-4 border-l-kp-500 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-start gap-3">
                    <div class="grid size-10 shrink-0 place-items-center rounded-full bg-kp-100 text-kp-700">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M20 12a8 8 0 1 1-2.34-5.66M20 4v6h-6"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">Procesando carga</h3>
                        <p class="mt-1 text-sm text-slate-600">La información está siendo validada y cargada.</p>
                        <p class="mt-2 text-xs text-slate-500">El estado se actualiza automáticamente.</p>
                    </div>
                </div>
                <a href="{{ route('imports.show', $batch->batch_id) }}" class="kp-btn-secondary whitespace-nowrap">Actualizar estado</a>
            </section>
        @elseif ($importStatus === \App\ImportStatus::Completed)
            <section class="kp-panel mb-5 flex flex-col gap-4 border-l-4 border-l-emerald-500 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-start gap-3">
                    <div class="grid size-10 shrink-0 place-items-center rounded-full bg-emerald-100 text-emerald-700">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m5 12 4 4L19 6"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">Procesamiento completado correctamente.</h3>
                        <p class="mt-1 text-sm text-slate-600">La información disponible fue validada y cargada.</p>
                    </div>
                </div>
                @if ($batch->tipo === \App\ImportType::Payments->value)
                    <a href="{{ route('payments.index') }}" class="kp-btn-primary whitespace-nowrap">Ver pagos</a>
                @else
                    <a href="{{ route('imports.index') }}" class="kp-btn-primary whitespace-nowrap">Volver a cargas</a>
                @endif
            </section>
        @elseif ($importStatus === \App\ImportStatus::CompletedWithErrors)
            <section class="kp-panel mb-5 flex flex-col gap-4 border-l-4 border-l-orange-500 p-5 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-start gap-3">
                    <div class="grid size-10 shrink-0 place-items-center rounded-full bg-orange-100 text-orange-700">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8v5m0 3h.01M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">Procesamiento completado con observaciones.</h3>
                        <p class="mt-1 text-sm text-slate-600">Algunas filas requieren revisión. Consulta el detalle para corregir el archivo de origen.</p>
                    </div>
                </div>
                <a href="#errores" class="kp-btn-secondary whitespace-nowrap">Revisar observaciones</a>
            </section>
        @elseif ($importStatus === \App\ImportStatus::Error)
            <section class="kp-panel mb-5 border-l-4 border-l-red-500 p-5">
                <div class="flex items-start gap-3">
                    <div class="grid size-10 shrink-0 place-items-center rounded-full bg-red-100 text-red-700">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke-width="1.8"/><path stroke-linecap="round" stroke-width="1.8" d="m9 9 6 6m0-6-6 6"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">La carga no pudo procesarse.</h3>
                        <p class="mt-1 text-sm text-slate-600">Verifica el archivo e intenta nuevamente mediante el flujo autorizado.</p>
                        @if (filled($batch->mensaje_error))
                            <p class="mt-3 text-sm font-medium text-red-800">{{ $batch->mensaje_error }}</p>
                        @endif
                    </div>
                </div>
            </section>
        @endif

        <section class="kp-panel overflow-hidden">
            <dl class="grid sm:grid-cols-3 sm:divide-x sm:divide-slate-200">
                @foreach ([
                    ['label' => 'Filas del archivo', 'value' => $batch->filas_archivo, 'color' => 'text-slate-950'],
                    ['label' => 'Cargadas', 'value' => $batch->filas_insertadas, 'color' => 'text-emerald-700'],
                    ['label' => 'Con error', 'value' => $batch->filas_error, 'color' => (int) $batch->filas_error > 0 ? 'text-red-700' : 'text-slate-950'],
                ] as $counter)
                    <div class="border-b border-slate-200 px-5 py-5 last:border-b-0 sm:border-b-0 sm:px-6">
                        <dt class="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">{{ $counter['label'] }}</dt>
                        <dd class="mt-2 text-3xl font-semibold tabular-nums tracking-[-0.03em] {{ $counter['color'] }}">{{ number_format((int) $counter['value']) }}</dd>
                    </div>
                @endforeach
            </dl>
        </section>

        <section class="kp-panel mt-5 overflow-hidden">
            <div class="border-b border-slate-200 px-5 py-4 sm:px-6">
                <h3 class="text-sm font-semibold text-slate-950">Información de la carga</h3>
            </div>
            <div class="grid lg:grid-cols-[1.15fr_1fr] lg:divide-x lg:divide-slate-200">
                <div class="p-5 sm:p-6">
                    <p class="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Archivo</p>
                    <div class="mt-3 flex items-start gap-3">
                        <div class="grid size-10 shrink-0 place-items-center rounded-lg bg-kp-50 text-kp-700">
                            <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M7 3h7l4 4v14H7V3Zm7 0v5h5"/></svg>
                        </div>
                        <div class="min-w-0 flex-1">
                            <p class="break-all text-sm font-semibold text-slate-900">{{ $batch->archivo_original ?? $batch->archivo }}</p>
                            <p class="mt-1 text-xs text-slate-500">
                                <x-file-size :bytes="$batch->archivo_tamano" /> · {{ \App\ImportType::tryFrom($batch->tipo)?->label() ?? $batch->tipo }}
                                @if (filled($batch->entidad))
                                    / {{ \App\FinancialEntity::tryFrom($batch->entidad)?->label() ?? $batch->entidad }}
                                @endif
                            </p>
                        </div>
                    </div>
                    @can('operate')
                        @if ($fileIsStored)
                            <a href="{{ route('imports.file', $batch->batch_id) }}" class="kp-btn-secondary mt-5">
                                <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 4v12m0 0 5-5m-5 5-5-5M5 20h14"/></svg>
                                Descargar archivo
                            </a>
                        @endif
                    @endcan
                </div>

                <div class="border-t border-slate-200 p-5 sm:p-6 lg:border-t-0">
                    <dl class="grid grid-cols-[minmax(7rem,0.45fr)_1fr] gap-x-4 gap-y-3.5 text-sm">
                        <dt class="text-slate-500">Origen</dt><dd class="font-medium text-slate-800">{{ \App\ImportOrigin::tryFrom($batch->origen)?->label() ?? $batch->origen }}</dd>
                        @if (filled($batch->entidad))
                            <dt class="text-slate-500">Entidad</dt><dd class="font-medium text-slate-800">{{ \App\FinancialEntity::tryFrom($batch->entidad)?->label() ?? $batch->entidad }}</dd>
                        @endif
                        <dt class="text-slate-500">Registrada</dt><dd class="text-slate-800"><x-utc-datetime :value="$batch->fecha_inicio" /></dd>
                        <dt class="text-slate-500">Finalizada</dt><dd class="text-slate-800"><x-utc-datetime :value="$batch->fecha_fin" /></dd>
                        <dt class="text-slate-500">Registrada por</dt><dd class="text-slate-800">{{ $batch->usuario_nombre }}</dd>
                    </dl>
                </div>
            </div>
        </section>

        @if ((int) $batch->filas_error > 0 || $errors->count() > 0)
            <section id="errores" class="kp-panel mt-5 scroll-mt-24 overflow-hidden">
                <div class="border-b border-slate-200 px-5 py-4 sm:flex sm:items-center sm:justify-between sm:px-6">
                    <div>
                        <h3 class="text-sm font-semibold text-slate-950">Observaciones del archivo</h3>
                        <p class="mt-1 text-xs text-slate-500">Revisa la fila, el campo y el motivo para corregir el archivo de origen.</p>
                    </div>
                    <span class="mt-2 inline-flex text-xs font-semibold text-red-700 sm:mt-0">{{ number_format((int) $batch->filas_error) }} filas con error</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
                        <thead class="bg-red-50/50">
                            <tr>
                                <th class="kp-table-heading">Fila</th>
                                <th class="kp-table-heading">Campo</th>
                                <th class="kp-table-heading">Valor recibido</th>
                                <th class="kp-table-heading">Observación</th>
                                <th class="kp-table-heading">Fecha</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            @forelse ($errors as $error)
                                <tr class="hover:bg-red-50/30">
                                    <td class="px-4 py-3.5 font-semibold tabular-nums text-slate-700">{{ $error->numero_fila }}</td>
                                    <td class="px-4 py-3.5"><span class="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">{{ $error->campo ?: '—' }}</span></td>
                                    <td class="max-w-xs truncate px-4 py-3.5 font-mono text-xs text-slate-600" title="{{ $error->valor }}">{{ $error->valor ?: '—' }}</td>
                                    <td class="min-w-64 px-4 py-3.5 text-red-800">{{ $error->error }}</td>
                                    <td class="whitespace-nowrap px-4 py-3.5 text-xs text-slate-500"><x-utc-datetime :value="$error->created_at" /></td>
                                </tr>
                            @empty
                                <tr><td colspan="5" class="px-6 py-10 text-center text-sm text-slate-500">El detalle de las observaciones aún no está disponible.</td></tr>
                            @endforelse
                        </tbody>
                    </table>
                </div>
                @if ($errors->hasPages())
                    <div class="border-t border-slate-200 px-4 py-3">{{ $errors->links() }}</div>
                @endif
            </section>
        @endif
    </div>
@endsection
