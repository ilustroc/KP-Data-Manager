@extends('layouts.app')

@section('title', 'Nueva carga')
@section('page-heading', 'Nueva carga')

@section('content')
    <div class="kp-page-shell">
        <x-page-header title="Nueva carga" subtitle="Selecciona el tipo de información y adjunta el archivo. La validación y el procesamiento comenzarán automáticamente." />

        <div class="kp-panel overflow-hidden">
            @if ($errors->any())
                <div class="border-b border-red-300 bg-red-50 px-3 py-2 text-[13px] text-red-900" role="alert">
                    <div class="flex items-start gap-3">
                        <svg class="mt-0.5 size-5 shrink-0 text-red-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v4m0 4h.01M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/></svg>
                        <div>
                            <p class="font-semibold">Revisa la información de la carga</p>
                            <ul class="mt-1.5 list-disc space-y-1 pl-5 text-red-800">
                        @foreach ($errors->all() as $error)
                            <li>{{ $error }}</li>
                        @endforeach
                            </ul>
                        </div>
                    </div>
                </div>
            @endif

            <form method="POST" action="{{ route('imports.store') }}" enctype="multipart/form-data">
                @csrf

                <div class="space-y-4 p-4">
                    <div class="border-b border-border pb-2">
                        <h3 class="text-[13px] font-semibold text-ink">Información de la carga</h3>
                        <p class="text-xs text-muted">Indica el tipo de información y su procedencia.</p>
                    </div>

                    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-import-type-fields>
                        <label class="kp-label">
                            Tipo de información
                            <select name="tipo" required class="kp-field normal-case tracking-normal" data-import-type>
                            @foreach ($types as $type)
                                <option value="{{ $type->value }}" @selected(old('tipo', \App\ImportType::Payments->value) === $type->value)>{{ $type->label() }}</option>
                            @endforeach
                            </select>
                        </label>

                        <label class="kp-label {{ old('tipo', \App\ImportType::Payments->value) === \App\ImportType::Portfolio->value ? '' : 'hidden' }}" data-financial-entity-field>
                            Entidad financiera
                            <select name="entidad" class="kp-field normal-case tracking-normal" data-financial-entity>
                                <option value="">Selecciona una entidad</option>
                                @foreach ($entities as $entity)
                                    <option value="{{ $entity->value }}" @selected(old('entidad') === $entity->value) @disabled(! $entity->isImplemented())>
                                        {{ $entity->label() }}{{ $entity->isImplemented() ? '' : ' · Próximamente' }}
                                    </option>
                                @endforeach
                            </select>
                            <span class="mt-1 block text-[11px] font-normal normal-case tracking-normal text-muted">Disponibles: BBVA, Caja Arequipa y Compartamos.</span>
                        </label>

                        <fieldset>
                            <legend class="kp-label">Origen</legend>
                            <div class="mt-1 grid grid-cols-3 gap-1.5">
                                @foreach ($origins as $origin)
                                    <label class="cursor-pointer">
                                        <input class="peer sr-only" type="radio" name="origen" value="{{ $origin->value }}" required @checked(old('origen', \App\ImportOrigin::Daily->value) === $origin->value)>
                                        <span class="flex h-[var(--control-height)] items-center justify-center rounded-control border border-slate-300 bg-white px-2 text-center text-[13px] font-medium normal-case tracking-normal text-slate-600 transition hover:border-slate-400 peer-checked:border-primary peer-checked:bg-blue-50 peer-checked:text-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary">{{ $origin->label() }}</span>
                                    </label>
                                @endforeach
                            </div>
                        </fieldset>
                    </div>

                    <div class="border-t border-border pt-4">
                        <label class="kp-label" for="archivo">Archivo a procesar</label>
                        <div class="mt-1 flex items-center gap-3 rounded-control border border-dashed border-slate-300 bg-slate-50 p-3">
                            <div class="grid size-8 shrink-0 place-items-center rounded-control bg-blue-100 text-primary">
                                <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4"/></svg>
                            </div>
                            <div class="min-w-0 flex-1">
                                <input id="archivo" type="file" name="archivo" required accept=".csv,.xlsx" class="block w-full text-[13px] text-slate-600 file:mr-3 file:rounded-control file:border file:border-slate-300 file:bg-white file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-700 hover:file:bg-slate-100">
                                <p class="mt-1 text-[11px] text-muted">CSV o XLSX · máximo {{ $maximumUploadMegabytes }} MB</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex flex-col-reverse gap-2 border-t border-border bg-slate-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-end">
                    <a href="{{ route('imports.index') }}" class="kp-btn-secondary">Cancelar</a>
                    <button type="submit" class="kp-btn-primary">
                        <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v14m-7-7h14"/></svg>
                        Cargar y procesar
                    </button>
                </div>
            </form>
        </div>
    </div>
@endsection
