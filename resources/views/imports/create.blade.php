@extends('layouts.app')

@section('title', 'Nueva carga')
@section('page-heading', 'Nueva carga')

@section('content')
    <div class="mx-auto max-w-4xl">
        <div class="mb-6">
            <h2 class="text-2xl font-semibold tracking-tight text-slate-950">Registrar archivo</h2>
            <p class="mt-1 text-sm text-slate-600">El archivo quedará resguardado y pendiente de procesamiento. En esta fase no se importan filas.</p>
        </div>

        <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
            @if ($errors->any())
                <div class="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
                    <p class="font-semibold">No se pudo registrar la carga.</p>
                    <ul class="mt-2 list-disc space-y-1 pl-5">
                        @foreach ($errors->all() as $error)
                            <li>{{ $error }}</li>
                        @endforeach
                    </ul>
                </div>
            @endif

            <form method="POST" action="{{ route('imports.store') }}" enctype="multipart/form-data" class="space-y-6">
                @csrf

                <div class="grid gap-5 md:grid-cols-2">
                    <label class="block text-sm font-medium text-slate-700">
                        Tipo
                        <select name="tipo" required class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kp-500">
                            @foreach ($types as $type)
                                <option value="{{ $type->value }}" @selected(old('tipo', \App\ImportType::Payments->value) === $type->value)>{{ $type->label() }}</option>
                            @endforeach
                        </select>
                    </label>

                    <label class="block text-sm font-medium text-slate-700">
                        Origen
                        <select name="origen" required class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kp-500">
                            @foreach ($origins as $origin)
                                <option value="{{ $origin->value }}" @selected(old('origen', \App\ImportOrigin::Daily->value) === $origin->value)>{{ $origin->label() }}</option>
                            @endforeach
                        </select>
                    </label>
                </div>

                <label class="block text-sm font-medium text-slate-700">
                    Archivo CSV o XLSX
                    <input type="file" name="archivo" required accept=".csv,.xlsx" class="mt-1.5 block w-full rounded-lg border border-slate-300 bg-white text-sm text-slate-700 file:mr-4 file:border-0 file:bg-slate-100 file:px-4 file:py-2.5 file:font-semibold file:text-slate-700 hover:file:bg-slate-200">
                    <span class="mt-2 block text-xs text-slate-500">Máximo web: {{ $maximumUploadMegabytes }} MB. Para históricos grandes usa el inbox privado y el comando de registro.</span>
                </label>

                <div class="flex flex-wrap gap-3 border-t border-slate-100 pt-5">
                    <button type="submit" class="rounded-lg bg-kp-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-kp-700">Registrar carga</button>
                    <a href="{{ route('imports.index') }}" class="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cancelar</a>
                </div>
            </form>
        </div>
    </div>
@endsection
