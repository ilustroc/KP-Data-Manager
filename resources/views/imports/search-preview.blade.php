@extends('layouts.app')

@section('title', 'Preview '.$preview->datasetCode)
@section('page-heading', 'Preview '.$preview->datasetCode)

@section('content')
    <div class="kp-page-shell">
        <x-page-header :title="'Preview '.$preview->datasetCode" subtitle="Revisa el archivo completo, corrige el mapping y confirma explícitamente antes de registrar el batch." />

        @if ($errors->any())
            <div class="kp-alert-error" role="alert">{{ $errors->first() }}</div>
        @endif

        @if ($preview->analysis)
            <div class="kp-panel overflow-hidden">
                <div class="grid gap-px bg-border sm:grid-cols-3 xl:grid-cols-6">
                    @foreach ([
                        'Filas' => $preview->analysis->totalRows,
                        'Válidas' => $preview->analysis->validRows,
                        'Con error' => $preview->analysis->invalidRows,
                        'Documentos' => $preview->analysis->uniqueDocuments,
                        ($preview->datasetCode === 'TELEFONOS' ? 'Teléfonos' : 'Registros únicos') => $preview->datasetCode === 'TELEFONOS' ? $preview->analysis->uniquePhones : ($preview->analysis->metrics['unique_emails'] ?? $preview->analysis->metrics['addresses'] ?? $preview->analysis->metrics['vehicles'] ?? $preview->analysis->metrics['properties'] ?? $preview->analysis->metrics['unique_records'] ?? 0),
                        'Duplicados' => $preview->datasetCode === 'TELEFONOS' ? $preview->analysis->duplicateDocumentPhones : ($preview->analysis->metrics['duplicates_exact'] ?? 0),
                    ] as $label => $value)
                        <div class="bg-white p-3"><span class="kp-label">{{ $label }}</span><p class="text-xl font-semibold">{{ number_format($value) }}</p></div>
                    @endforeach
                </div>
                @if (in_array($preview->datasetCode, ['SBS_RESUMEN', 'SBS_DETALLE', 'LABORAL_ESSALUD'], true))
                    <div class="grid gap-px border-t border-border bg-border sm:grid-cols-3">
                        <div class="bg-white p-3"><span class="kp-label">Periodos</span><p class="text-xl font-semibold">{{ number_format($preview->analysis->metrics['periods'] ?? 0) }}</p></div>
                        @if ($preview->datasetCode === 'SBS_DETALLE')
                            <div class="bg-white p-3"><span class="kp-label">Filas desplazadas recuperadas</span><p class="text-xl font-semibold">{{ number_format($preview->analysis->metrics['shifted_recovered'] ?? 0) }}</p></div>
                        @endif
                    </div>
                @endif
                <div class="border-t border-border px-4 py-3 text-sm font-semibold {{ $preview->analysis->isReady() ? 'text-emerald-700' : 'text-red-700' }}">
                    {{ $preview->analysis->isReady() ? '✓ Archivo listo para procesar' : '✕ Archivo no apto para procesar' }}
                </div>
            </div>
        @endif

        @if ($preview->analysis && $preview->analysis->warningsTotal > 0)
            <section class="kp-panel mt-3 overflow-hidden" aria-labelledby="warning-summary-title">
                <div class="border-b border-border px-4 py-3">
                    <h2 id="warning-summary-title" class="text-sm font-semibold text-ink">Advertencias</h2>
                    <p class="mt-0.5 text-xs text-muted">Las advertencias no bloquean la publicación; los registros repetidos exactos o direcciones vacías no se enviarán a Silver/Gold.</p>
                </div>
                <div class="grid gap-px bg-border sm:grid-cols-3">
                    <div class="bg-white px-4 py-3"><span class="kp-label">Duplicados exactos</span><p class="mt-1 text-xl font-semibold">{{ number_format($preview->analysis->metrics['duplicates_exact'] ?? 0) }}</p></div>
                    <div class="bg-white px-4 py-3"><span class="kp-label">Direcciones vacías</span><p class="mt-1 text-xl font-semibold">{{ number_format($preview->analysis->metrics['empty_address_rows'] ?? 0) }}</p></div>
                    <div class="bg-white px-4 py-3"><span class="kp-label">Total advertencias</span><p class="mt-1 text-xl font-semibold">{{ number_format($preview->analysis->warningsTotal) }}</p></div>
                </div>
            </section>
        @endif

        @if ($preview->analysis && $preview->analysis->totalErrors > 0)
            <section class="kp-panel mt-3 overflow-hidden" aria-labelledby="error-summary-title">
                <div class="flex flex-col gap-3 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h2 id="error-summary-title" class="text-sm font-semibold text-ink">Resumen de errores</h2>
                        <p class="mt-0.5 text-xs text-muted">Descarga el detalle completo para corregir el archivo fuente.</p>
                    </div>
                    <a href="{{ route('imports.search.preview.errors', $preview->token) }}" class="kp-btn-secondary whitespace-nowrap">Descargar errores</a>
                </div>
                <dl class="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-5">
                    @foreach ([
                        'Fechas inválidas' => $preview->analysis->invalidDates,
                        'Teléfonos inválidos' => $preview->analysis->invalidPhones,
                        'Documentos inválidos' => $preview->analysis->invalidDocuments,
                        'Duplicados' => $preview->analysis->duplicateDocumentPhones,
                        'Total' => $preview->analysis->totalErrors,
                    ] as $label => $value)
                        <div class="bg-white px-4 py-3">
                            <dt class="kp-label">{{ $label }}</dt>
                            <dd class="mt-1 text-xl font-semibold tabular-nums text-ink">{{ number_format($value) }}</dd>
                        </div>
                    @endforeach
                    @if ($preview->analysis->invalidOperators > 0 || $preview->analysis->ambiguousOperators > 0)
                        <div class="bg-white px-4 py-3 sm:col-span-2 xl:col-span-5">
                            <p class="text-xs text-amber-800">
                                Operadores no reconocidos: {{ number_format($preview->analysis->invalidOperators) }} ·
                                Operadores ambiguos: {{ number_format($preview->analysis->ambiguousOperators) }}
                            </p>
                        </div>
                    @endif
                </dl>
            </section>
        @endif

        <div class="kp-panel mt-3 overflow-hidden">
            <div class="grid gap-px border-b border-border bg-border md:grid-cols-4">
                <div class="bg-white p-3"><span class="kp-label">Dataset</span><p class="text-sm">{{ $preview->datasetCode }}</p></div>
                <div class="bg-white p-3"><span class="kp-label">Fuente</span><p class="text-sm">{{ $preview->sourceCode }}</p></div>
                <div class="bg-white p-3"><span class="kp-label">Modo</span><p class="text-sm">{{ $preview->refreshMode }}</p></div>
                <div class="bg-white p-3"><span class="kp-label">Archivo</span><p class="truncate text-sm">{{ $preview->metadata->originalName }}</p></div>
            </div>

            <form method="POST" action="{{ route('imports.search.confirm') }}">
                @csrf
                <input type="hidden" name="token" value="{{ $preview->token }}">

                <div class="p-4">
                    <h2 class="text-sm font-semibold">Mapping canónico</h2>
                    <div class="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                        @foreach ($fields as $target => $label)
                            <label class="kp-label">
                                {{ $label }}
                                <select name="mapping[{{ $target }}]" required class="kp-field normal-case tracking-normal">
                                    <option value="">Selecciona columna</option>
                                    @foreach ($preview->headers as $header)
                                        <option value="{{ $header }}" @selected(old("mapping.{$target}", $preview->suggestedMapping[$target] ?? '') === $header)>{{ $header }}</option>
                                    @endforeach
                                </select>
                            </label>
                        @endforeach
                    </div>
                </div>

                <div class="overflow-x-auto border-y border-border">
                    <table class="kp-table min-w-[760px]">
                        <thead><tr>@foreach ($preview->headers as $header)<th class="whitespace-nowrap px-4">{{ $header }}</th>@endforeach</tr></thead>
                        <tbody>
                            @forelse ($preview->rows as $row)
                                <tr class="divide-x divide-border">@foreach ($row as $value)<td class="max-w-72 truncate px-4">{{ $value }}</td>@endforeach</tr>
                            @empty
                                <tr><td colspan="{{ count($preview->headers) }}" class="text-center text-muted">No se detectaron filas de datos en el preview.</td></tr>
                            @endforelse
                        </tbody>
                    </table>
                </div>

                @if ($preview->analysis && $preview->analysis->totalErrors > 0)
                    <div class="border-t border-border p-4">
                        <h2 class="text-sm font-semibold">Primeros errores detectados ({{ number_format($preview->analysis->totalErrors) }})</h2>
                        <p class="mt-1 text-xs text-muted">Se muestran como máximo {{ count($preview->analysis->errors) }} errores, con identificadores enmascarados. Usa la descarga para obtener el detalle completo.</p>
                        <div class="mt-3 overflow-x-auto">
                            <table class="kp-table min-w-full">
                                <thead><tr><th>Fila</th><th>Documento</th><th>Teléfono</th><th>Campo</th><th>Error</th></tr></thead>
                                <tbody>
                                    @foreach ($preview->analysis->errors as $error)
                                        <tr><td>{{ $error['row'] }}</td><td>{{ $error['document'] }}</td><td>{{ $error['phone'] }}</td><td>{{ $error['field'] }}</td><td><span class="block">{{ $error['message'] }}</span><span class="text-[11px] text-muted">{{ $error['error'] }}</span></td></tr>
                                    @endforeach
                                </tbody>
                            </table>
                        </div>
                    </div>
                @endif

                <div class="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <label class="flex items-start gap-2 text-[13px] text-slate-700">
                        <input type="checkbox" name="confirmacion" value="1" required class="mt-0.5">
                        Confirmo que el mapping y el modo de actualización son correctos.
                    </label>
                    <div class="flex gap-2">
                        <a href="{{ route('imports.create') }}" class="kp-btn-secondary">Cancelar</a>
                        <button type="submit" class="kp-btn-primary" @disabled($preview->analysis && ! $preview->analysis->isReady())>Confirmar y procesar</button>
                    </div>
                </div>
            </form>
        </div>
    </div>
@endsection
