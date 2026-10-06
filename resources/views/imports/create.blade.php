@extends('layouts.app')

@section('title', 'Nueva carga')
@section('page-heading', 'Nueva carga')

@section('content')
    <div class="mx-auto max-w-5xl">
        <div class="mb-7">
            <p class="kp-eyebrow">Cargas</p>
            <h2 class="mt-2 text-2xl font-semibold tracking-[-0.02em] text-slate-950 sm:text-3xl">Nueva carga</h2>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Selecciona el tipo de información y adjunta el archivo. La validación y el procesamiento comenzarán automáticamente.</p>
        </div>

        <div class="kp-panel overflow-hidden">
            @if ($errors->any())
                <div class="border-b border-red-200 bg-red-50 px-5 py-4 text-sm text-red-900 sm:px-7" role="alert">
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

                <div class="space-y-7 p-5 sm:p-7">
                    <div>
                        <h3 class="text-sm font-semibold text-slate-950">Información de la carga</h3>
                        <p class="mt-1 text-sm text-slate-500">Indica el tipo de información y su procedencia.</p>
                    </div>

                    <div class="grid gap-5 md:grid-cols-2" data-import-type-fields>
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
                            <span class="mt-1.5 block text-xs font-normal normal-case tracking-normal text-slate-500">Actualmente disponible: BBVA.</span>
                        </label>

                        <fieldset>
                            <legend class="kp-label">Origen</legend>
                            <div class="mt-1.5 grid grid-cols-3 gap-2">
                                @foreach ($origins as $origin)
                                    <label class="cursor-pointer">
                                        <input class="peer sr-only" type="radio" name="origen" value="{{ $origin->value }}" required @checked(old('origen', \App\ImportOrigin::Daily->value) === $origin->value)>
                                        <span class="flex min-h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-2 text-center text-sm font-medium normal-case tracking-normal text-slate-600 transition hover:border-slate-400 peer-checked:border-kp-600 peer-checked:bg-kp-50 peer-checked:text-kp-800 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-kp-500">{{ $origin->label() }}</span>
                                    </label>
                                @endforeach
                            </div>
                        </fieldset>
                    </div>

                    <div class="border-t border-slate-200 pt-7">
                        <label class="kp-label" for="archivo">Archivo a procesar</label>
                        <div class="mt-2 rounded-xl border border-dashed border-slate-300 bg-slate-50/70 p-5 sm:flex sm:items-center sm:gap-5">
                            <div class="mb-4 grid size-11 shrink-0 place-items-center rounded-lg bg-kp-100 text-kp-700 sm:mb-0">
                                <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4"/></svg>
                            </div>
                            <div class="min-w-0 flex-1">
                                <input id="archivo" type="file" name="archivo" required accept=".csv,.xlsx" class="block w-full text-sm text-slate-600 file:mr-4 file:rounded-md file:border-0 file:bg-slate-200 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-slate-700 hover:file:bg-slate-300">
                                <p class="mt-2 text-xs leading-5 text-slate-500">Formatos permitidos: CSV y XLSX. Tamaño máximo: {{ $maximumUploadMegabytes }} MB.</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex flex-col-reverse gap-3 border-t border-slate-200 bg-slate-50/60 px-5 py-4 sm:flex-row sm:items-center sm:justify-end sm:px-7">
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
