@if ($errors->any())
    <div class="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
        <p class="font-semibold">Revisa los filtros ingresados.</p>
        <ul class="mt-2 list-disc space-y-1 pl-5">
            @foreach ($errors->all() as $error)
                <li>{{ $error }}</li>
            @endforeach
        </ul>
    </div>
@endif

<form method="GET" action="{{ route('imports.index') }}" class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label class="block text-sm font-medium text-slate-700">
            Batch
            <input type="number" name="batch_id" min="1" value="{{ old('batch_id', $filters['batch_id'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Tipo
            <select name="tipo" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
                <option value="">Todos</option>
                @foreach ($types as $type)
                    <option value="{{ $type->value }}" @selected(($filters['tipo'] ?? '') === $type->value)>{{ $type->label() }}</option>
                @endforeach
            </select>
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Origen
            <select name="origen" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
                <option value="">Todos</option>
                @foreach ($origins as $origin)
                    <option value="{{ $origin->value }}" @selected(($filters['origen'] ?? '') === $origin->value)>{{ $origin->label() }}</option>
                @endforeach
            </select>
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Estado
            <select name="estado" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
                <option value="">Todos</option>
                @foreach ($statuses as $status)
                    <option value="{{ $status->value }}" @selected(($filters['estado'] ?? '') === $status->value)>{{ $status->label() }}</option>
                @endforeach
            </select>
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Fecha desde
            <input type="date" name="fecha_desde" value="{{ old('fecha_desde', $filters['fecha_desde'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Fecha hasta
            <input type="date" name="fecha_hasta" value="{{ old('fecha_hasta', $filters['fecha_hasta'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Nombre de archivo
            <input type="text" name="nombre_archivo" maxlength="255" value="{{ old('nombre_archivo', $filters['nombre_archivo'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Usuario auditor
            <input type="text" name="usuario" maxlength="100" value="{{ old('usuario', $filters['usuario'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Filas por página
            <select name="per_page" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
                @foreach ([25, 50, 100] as $size)
                    <option value="{{ $size }}" @selected((int) ($filters['per_page'] ?? 25) === $size)>{{ $size }}</option>
                @endforeach
            </select>
        </label>
    </div>

    <div class="mt-5 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
        <button type="submit" class="rounded-lg bg-kp-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-kp-700">Buscar</button>
        <a href="{{ route('imports.index') }}" class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Limpiar filtros</a>
    </div>
</form>
