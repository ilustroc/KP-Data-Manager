@extends('layouts.app')

@section('title', 'Carga #'.$batch->batch_id)
@section('page-heading', 'Detalle de carga')

@section('content')
    <div class="mx-auto max-w-6xl">
        <div class="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
                <h2 class="text-2xl font-semibold tracking-tight text-slate-950">Carga #{{ $batch->batch_id }}</h2>
                <p class="mt-1 break-all text-sm text-slate-600">{{ $batch->archivo_original ?? $batch->archivo }}</p>
            </div>
            <div class="flex flex-wrap gap-3">
                <a href="{{ route('imports.index') }}" class="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Volver a cargas</a>
            </div>
        </div>

        @if ($batch->estado === \App\ImportStatus::Pending->value)
            <div class="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-950">
                <p class="font-semibold">Preparando procesamiento...</p>
            </div>
        @elseif ($batch->estado === \App\ImportStatus::Processing->value)
            <div class="mb-6 flex flex-col gap-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-4 text-sm text-blue-950 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <p class="font-semibold">Procesando carga</p>
                    <p class="mt-1 text-blue-800">La información está siendo validada y cargada.</p>
                </div>
                <a href="{{ route('imports.show', $batch->batch_id) }}" class="whitespace-nowrap rounded-lg border border-blue-300 bg-white px-4 py-2.5 font-semibold text-blue-800 hover:bg-blue-100">
                    Actualizar estado
                </a>
            </div>
        @elseif ($batch->estado === \App\ImportStatus::Completed->value)
            <div class="mb-6 flex flex-col gap-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-950 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <p class="font-semibold">Procesamiento completado</p>
                    <p class="mt-1 text-emerald-800">{{ number_format((int) $batch->filas_archivo) }} filas procesadas, {{ number_format((int) $batch->filas_insertadas) }} filas cargadas y {{ number_format((int) $batch->filas_error) }} filas con errores.</p>
                </div>
                <div class="flex flex-wrap gap-3">
                    <a href="{{ route('payments.index') }}" class="rounded-lg bg-emerald-700 px-4 py-2.5 font-semibold text-white hover:bg-emerald-800">Ver pagos</a>
                    <a href="{{ route('imports.index') }}" class="rounded-lg border border-emerald-300 bg-white px-4 py-2.5 font-semibold text-emerald-800 hover:bg-emerald-100">Volver a cargas</a>
                </div>
            </div>
        @elseif ($batch->estado === \App\ImportStatus::CompletedWithErrors->value)
            <div class="mb-6 flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-950 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <p class="font-semibold">Procesamiento completado con observaciones</p>
                    <p class="mt-1 text-amber-800">Se cargaron {{ number_format((int) $batch->filas_insertadas) }} filas y {{ number_format((int) $batch->filas_error) }} quedaron con error.</p>
                </div>
                <a href="#errores" class="font-semibold text-amber-900 underline decoration-amber-400 underline-offset-4">Ver errores</a>
            </div>
        @elseif ($batch->estado === \App\ImportStatus::Error->value)
            <div class="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-950">
                <p class="font-semibold">No se pudo procesar la carga.</p>
            </div>
        @endif

        <div class="grid gap-6 lg:grid-cols-2">
            <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div class="mb-4 flex items-center justify-between gap-3">
                    <h3 class="font-semibold text-slate-950">Registro</h3>
                    <x-import-status-badge :status="$batch->estado" />
                </div>
                <dl class="grid grid-cols-[minmax(8rem,0.45fr)_1fr] gap-x-4 gap-y-3 text-sm">
                    <dt class="text-slate-500">Tipo</dt><dd>{{ \App\ImportType::tryFrom($batch->tipo)?->label() ?? $batch->tipo }}</dd>
                    <dt class="text-slate-500">Origen</dt><dd>{{ \App\ImportOrigin::tryFrom($batch->origen)?->label() ?? $batch->origen }}</dd>
                    <dt class="text-slate-500">Fecha inicio</dt><dd><x-utc-datetime :value="$batch->fecha_inicio" /></dd>
                    <dt class="text-slate-500">Fecha fin</dt><dd><x-utc-datetime :value="$batch->fecha_fin" /></dd>
                    <dt class="text-slate-500">Usuario</dt><dd class="font-mono text-xs">{{ $batch->usuario ?: '—' }}</dd>
                </dl>
            </section>

            <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 class="mb-4 font-semibold text-slate-950">Archivo</h3>
                <p class="break-all text-sm font-medium text-slate-900">{{ $batch->archivo_original ?? $batch->archivo }}</p>
                <p class="mt-1 text-sm text-slate-500"><x-file-size :bytes="$batch->archivo_tamano" /></p>
                @can('operate')
                    @if ($fileIsStored)
                        <a href="{{ route('imports.file', $batch->batch_id) }}" class="mt-5 inline-flex rounded-lg bg-kp-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-kp-700">Descargar archivo</a>
                    @endif
                @endcan
            </section>
        </div>

        <section class="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 class="mb-4 font-semibold text-slate-950">Contadores</h3>
            <dl class="grid gap-4 sm:grid-cols-3">
                @foreach (['Procesadas' => $batch->filas_archivo, 'Cargadas' => $batch->filas_insertadas, 'Con error' => $batch->filas_error] as $label => $value)
                    <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <dt class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ $label }}</dt>
                        <dd class="mt-2 text-2xl font-semibold tabular-nums text-slate-950">{{ number_format((int) $value) }}</dd>
                    </div>
                @endforeach
            </dl>
            @if (filled($batch->mensaje_error))
                <div class="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    <p class="font-semibold">Mensaje de error</p>
                    <p class="mt-1 whitespace-pre-wrap">{{ $batch->mensaje_error }}</p>
                </div>
            @endif
        </section>

        <section id="errores" class="mt-6 scroll-mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div class="border-b border-slate-200 px-5 py-4"><h3 class="font-semibold text-slate-950">Errores</h3></div>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
                    <thead class="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <tr><th class="px-4 py-3">Fila</th><th class="px-4 py-3">Campo</th><th class="px-4 py-3">Valor</th><th class="px-4 py-3">Error</th><th class="px-4 py-3">Fecha</th></tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100">
                        @forelse ($errors as $error)
                            <tr>
                                <td class="px-4 py-3 font-mono">{{ $error->numero_fila }}</td>
                                <td class="px-4 py-3">{{ $error->campo ?: '—' }}</td>
                                <td class="max-w-xs truncate px-4 py-3" title="{{ $error->valor }}">{{ $error->valor ?: '—' }}</td>
                                <td class="px-4 py-3 text-red-700">{{ $error->error }}</td>
                                <td class="whitespace-nowrap px-4 py-3"><x-utc-datetime :value="$error->created_at" /></td>
                            </tr>
                        @empty
                            <tr><td colspan="5" class="px-6 py-10 text-center text-slate-500">No se registraron errores para esta carga.</td></tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
            @if ($errors->hasPages())
                <div class="border-t border-slate-200 px-4 py-3">{{ $errors->links() }}</div>
            @endif
        </section>
    </div>
@endsection
