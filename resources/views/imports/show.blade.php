@extends('layouts.app')

@section('title', 'Carga #'.$batch->batch_id)
@section('page-heading', 'Detalle de carga')

@php
    $importStatus = \App\ImportStatus::tryFrom((string) $batch->estado);
    $refreshesAutomatically = in_array($importStatus, [\App\ImportStatus::Pending, \App\ImportStatus::Processing], true);
@endphp

@section('content')
    <div class="kp-page-shell" @if ($refreshesAutomatically) data-auto-refresh-url="{{ route('imports.show', $batch->batch_id) }}" data-auto-refresh-after="8000" @endif>
        <a href="{{ route('imports.index') }}" class="mb-2 inline-flex items-center gap-1 text-xs font-semibold text-muted hover:text-primary">
            <span aria-hidden="true">←</span>
            Cargas
        </a>

        <div class="mb-3 flex flex-col gap-3 border-b border-border pb-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                    <h2 class="kp-page-title">Carga #{{ $batch->batch_id }} · <span class="font-medium">{{ $batch->archivo_original ?? $batch->archivo }}</span></h2>
                    <x-import-status-badge :status="$batch->estado" />
                </div>
                <p class="kp-page-subtitle">
                    @if (filled($batch->entidad))
                        {{ \App\FinancialEntity::tryFrom($batch->entidad)?->label() ?? $batch->entidad }} ·
                    @endif
                    @if (filled($batch->dataset_code))
                        {{ $batch->dataset_code }} · {{ $batch->source_code }} · {{ $batch->refresh_mode }} ·
                    @endif
                    @if ($batch->tipo !== \App\ImportType::Search->value)
                        {{ \App\ImportOrigin::tryFrom($batch->origen)?->label() ?? $batch->origen }} ·
                    @endif
                    <x-utc-datetime :value="$batch->fecha_inicio" />
                </p>
            </div>
            <div class="flex shrink-0 flex-wrap gap-2">
                @can('operate')
                    @if ($fileIsStored)
                        <a href="{{ route('imports.file', $batch->batch_id) }}" class="kp-btn-secondary">
                            <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 4v12m0 0 5-5m-5 5-5-5M5 20h14"/></svg>
                            Descargar
                        </a>
                    @endif
                @endcan
                @can('administer')
                    @if ($deletionAllowed)
                        <button type="button" class="kp-btn-danger" data-import-deletion-open>Eliminar carga</button>
                    @endif
                @endcan
            </div>
        </div>

        @if ($importStatus === \App\ImportStatus::Pending)
            <section class="kp-panel mb-3 flex flex-col gap-3 border-l-[3px] border-l-amber-500 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-start gap-3">
                    <div class="grid size-8 shrink-0 place-items-center rounded-control bg-amber-100 text-amber-700">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke-width="1.8"/><path stroke-linecap="round" stroke-width="1.8" d="M12 7v5l3 2"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">Preparando procesamiento...</h3>
                        <p class="text-[13px] text-muted">Carga registrada y enviada a procesamiento. El estado se actualiza automáticamente.</p>
                    </div>
                </div>
                <a href="{{ route('imports.show', $batch->batch_id) }}" class="kp-btn-secondary whitespace-nowrap">Actualizar estado</a>
            </section>
        @elseif ($importStatus === \App\ImportStatus::Processing)
            <section class="kp-panel mb-3 flex flex-col gap-3 border-l-[3px] border-l-primary p-3 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-start gap-3">
                    <div class="grid size-8 shrink-0 place-items-center rounded-control bg-blue-100 text-primary">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M20 12a8 8 0 1 1-2.34-5.66M20 4v6h-6"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">Procesando carga</h3>
                        <p class="text-[13px] text-muted">La información está siendo validada y cargada. El estado se actualiza automáticamente.</p>
                    </div>
                </div>
                <a href="{{ route('imports.show', $batch->batch_id) }}" class="kp-btn-secondary whitespace-nowrap">Actualizar estado</a>
            </section>
        @elseif ($importStatus === \App\ImportStatus::Completed)
            <section class="kp-panel mb-3 flex flex-col gap-3 border-l-[3px] border-l-emerald-500 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-start gap-3">
                    <div class="grid size-8 shrink-0 place-items-center rounded-control bg-emerald-100 text-emerald-700">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m5 12 4 4L19 6"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">Procesamiento completado correctamente.</h3>
                        <p class="text-[13px] text-muted">La información disponible fue validada y cargada.</p>
                    </div>
                </div>
                @if ($batch->tipo === \App\ImportType::Payments->value)
                    <a href="{{ route('payments.index') }}" class="kp-btn-primary whitespace-nowrap">Ver pagos</a>
                @else
                    <a href="{{ route('imports.index') }}" class="kp-btn-primary whitespace-nowrap">Volver a cargas</a>
                @endif
            </section>
        @elseif ($importStatus === \App\ImportStatus::CompletedWithErrors)
            <section class="kp-panel mb-3 flex flex-col gap-3 border-l-[3px] border-l-orange-500 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex items-start gap-3">
                    <div class="grid size-8 shrink-0 place-items-center rounded-control bg-orange-100 text-orange-700">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8v5m0 3h.01M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/></svg>
                    </div>
                    <div>
                        <h3 class="font-semibold text-slate-950">Procesamiento completado con observaciones.</h3>
                        <p class="text-[13px] text-muted">Algunas filas requieren revisión. Consulta el detalle para corregir el archivo de origen.</p>
                    </div>
                </div>
                <a href="#errores" class="kp-btn-secondary whitespace-nowrap">Revisar observaciones</a>
            </section>
        @elseif ($importStatus === \App\ImportStatus::Error)
            <section class="kp-panel mb-3 border-l-[3px] border-l-red-500 p-3">
                <div class="flex items-start gap-3">
                    <div class="grid size-8 shrink-0 place-items-center rounded-control bg-red-100 text-red-700">
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

        <section class="kp-kpi-strip sm:grid-cols-3 xl:grid-cols-3">
            <dl class="contents">
                @foreach ([
                    ['label' => 'Filas del archivo', 'value' => $batch->filas_archivo, 'color' => 'text-slate-950'],
                    ['label' => 'Cargadas', 'value' => $batch->filas_insertadas, 'color' => 'text-emerald-700'],
                    ['label' => 'Con error', 'value' => $batch->filas_error, 'color' => (int) $batch->filas_error > 0 ? 'text-red-700' : 'text-slate-950'],
                ] as $counter)
                    <div class="kp-kpi-item">
                        <dt class="text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">{{ $counter['label'] }}</dt>
                        <dd class="mt-1 text-2xl font-semibold tabular-nums tracking-[-0.025em] {{ $counter['color'] }}">{{ number_format((int) $counter['value']) }}</dd>
                    </div>
                @endforeach
            </dl>
        </section>

        <section class="kp-panel mt-3 overflow-hidden">
            <div class="kp-section-header">
                <h3 class="text-[13px] font-semibold text-ink">Información de la carga</h3>
            </div>
            <div class="grid lg:grid-cols-[1fr_1.4fr] lg:divide-x lg:divide-border">
                <div class="p-3">
                    <p class="text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">Archivo</p>
                    <div class="mt-2 flex items-start gap-2.5">
                        <div class="grid size-8 shrink-0 place-items-center rounded-control bg-blue-100 text-primary">
                            <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M7 3h7l4 4v14H7V3Zm7 0v5h5"/></svg>
                        </div>
                        <div class="min-w-0 flex-1">
                            <p class="break-all text-[13px] font-semibold text-ink">{{ $batch->archivo_original ?? $batch->archivo }}</p>
                            <p class="text-[11px] text-muted">
                                <x-file-size :bytes="$batch->archivo_tamano" /> · {{ \App\ImportType::tryFrom($batch->tipo)?->label() ?? $batch->tipo }}
                                @if (filled($batch->entidad))
                                    / {{ \App\FinancialEntity::tryFrom($batch->entidad)?->label() ?? $batch->entidad }}
                                @endif
                            </p>
                        </div>
                    </div>
                </div>

                <div class="border-t border-border p-3 lg:border-t-0">
                    <dl class="grid gap-x-3 gap-y-2 text-[13px] sm:grid-cols-[6rem_1fr_6rem_1fr]">
                        @if ($batch->tipo !== \App\ImportType::Search->value)
                            <dt class="text-muted">Origen</dt><dd class="font-medium text-ink">{{ \App\ImportOrigin::tryFrom($batch->origen)?->label() ?? $batch->origen }}</dd>
                        @endif
                        @if (filled($batch->entidad))
                            <dt class="text-muted">Entidad</dt><dd class="font-medium text-ink">{{ \App\FinancialEntity::tryFrom($batch->entidad)?->label() ?? $batch->entidad }}</dd>
                        @endif
                        @if (filled($batch->dataset_code))
                            <dt class="text-muted">Dataset</dt><dd class="font-medium text-ink">{{ $batch->dataset_code }}</dd>
                            <dt class="text-muted">Fuente</dt><dd class="font-medium text-ink">{{ $batch->source_code }}</dd>
                            <dt class="text-muted">Modo</dt><dd class="font-medium text-ink">{{ $batch->refresh_mode }}</dd>
                            <dt class="text-muted">Mapping</dt><dd class="font-medium text-ink">v{{ $batch->mapping_version }}</dd>
                            <dt class="text-muted">Scope</dt><dd class="font-medium text-ink">{{ number_format((int) ($batch->scope_count ?? 0)) }}</dd>
                            <dt class="text-muted">Publicadas</dt><dd class="font-medium text-ink">{{ number_format((int) ($batch->rows_published ?? 0)) }}</dd>
                        @endif
                        <dt class="text-muted">Registrada</dt><dd class="text-ink"><x-utc-datetime :value="$batch->fecha_inicio" /></dd>
                        <dt class="text-muted">Finalizada</dt><dd class="text-ink"><x-utc-datetime :value="$batch->fecha_fin" /></dd>
                        <dt class="text-muted">Usuario</dt><dd class="text-ink sm:col-span-3">{{ $batch->usuario_nombre }}</dd>
                    </dl>
                </div>
            </div>
        </section>

        @can('administer')
            @if ($deletionAllowed)
                <dialog class="kp-modal" data-import-deletion-dialog @if ($errors->has('confirmation')) data-import-deletion-auto-open @endif role="dialog" aria-modal="true" aria-labelledby="delete-import-title" aria-describedby="delete-import-description">
                    <form method="POST" action="{{ route('imports.destroy', $batch->batch_id) }}" data-import-deletion-form>
                        @csrf
                        @method('DELETE')
                        <div class="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
                            <div>
                                <p class="text-[10px] font-semibold uppercase tracking-[0.08em] text-red-700">Acción irreversible</p>
                                <h2 id="delete-import-title" class="mt-0.5 text-lg font-semibold text-ink">Eliminar carga #{{ $batch->batch_id }}</h2>
                            </div>
                            <button type="button" class="grid size-7 place-items-center rounded-control text-slate-500 hover:bg-slate-100 hover:text-ink" aria-label="Cerrar confirmación" data-import-deletion-close>✕</button>
                        </div>

                        <div class="p-4">
                            <div id="delete-import-description" class="rounded-control border border-red-200 bg-red-50 p-3 text-[13px] text-red-900">
                                <p>Se eliminarán los datos cargados, sus observaciones y el archivo XLSX/CSV privado.</p>
                                <p class="mt-1 font-semibold">Esta acción no se puede deshacer desde la aplicación.</p>
                            </div>

                            <label for="deletion-confirmation" class="mt-4 block text-[13px] font-semibold text-ink">Escribe <span class="font-bold text-red-700">ELIMINAR</span> para confirmar</label>
                            <input id="deletion-confirmation" name="confirmation" type="text" value="{{ old('confirmation') }}" autocomplete="off" spellcheck="false" class="kp-input" data-import-deletion-confirmation>
                            @error('confirmation')
                                <p class="mt-1 text-xs font-medium text-red-700">{{ $message }}</p>
                            @enderror
                        </div>

                        <div class="flex flex-col-reverse gap-2 border-t border-border bg-slate-50 px-4 py-3 sm:flex-row sm:justify-end">
                            <button type="button" class="kp-btn-secondary" data-import-deletion-close>Cancelar</button>
                            <button type="submit" class="kp-btn-danger" disabled data-import-deletion-submit>
                                Eliminar definitivamente
                            </button>
                        </div>
                    </form>
                </dialog>
            @endif
        @endcan

        @if ((int) $batch->filas_error > 0 || $importErrors->count() > 0)
            <section id="errores" class="kp-panel mt-3 scroll-mt-16 overflow-hidden">
                <div class="kp-section-header">
                    <div>
                        <h3 class="text-[13px] font-semibold text-ink">Observaciones del archivo</h3>
                        <p class="text-[11px] text-muted">Revisa la fila, el campo y el motivo para corregir el archivo de origen.</p>
                    </div>
                    <span class="mt-2 inline-flex text-xs font-semibold text-red-700 sm:mt-0">{{ number_format((int) $batch->filas_error) }} filas con error</span>
                </div>
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-border text-left">
                        <thead class="bg-slate-100/80">
                            <tr>
                                <th class="kp-table-heading">Fila</th>
                                <th class="kp-table-heading">Campo</th>
                                <th class="kp-table-heading">Valor recibido</th>
                                <th class="kp-table-heading">Observación</th>
                                <th class="kp-table-heading">Fecha</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-border">
                            @forelse ($importErrors as $error)
                                <tr class="hover:bg-red-50/25">
                                    <td class="kp-table-cell font-semibold tabular-nums text-slate-700">{{ $error->numero_fila }}</td>
                                    <td class="kp-table-cell"><span class="rounded-control bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold text-slate-700">{{ $error->campo ?: '—' }}</span></td>
                                    <td class="kp-table-cell max-w-xs truncate font-mono text-xs text-slate-600" title="{{ $error->valor }}">{{ $error->valor ?: '—' }}</td>
                                    <td class="kp-table-cell min-w-64 text-red-800">{{ $error->error }}</td>
                                    <td class="kp-table-cell whitespace-nowrap text-xs text-muted"><x-utc-datetime :value="$error->created_at" /></td>
                                </tr>
                            @empty
                                <tr><td colspan="5" class="px-6 py-10 text-center text-sm text-slate-500">El detalle de las observaciones aún no está disponible.</td></tr>
                            @endforelse
                        </tbody>
                    </table>
                </div>
                @if ($importErrors->hasPages())
                    <div class="border-t border-slate-200 px-4 py-3">{{ $importErrors->links() }}</div>
                @endif
            </section>
        @endif
    </div>
@endsection
