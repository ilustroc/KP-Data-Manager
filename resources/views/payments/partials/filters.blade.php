@php
    $filters = $filters ?? [];
    $showDocument = $showDocument ?? true;
    $showStatus = $showStatus ?? true;
@endphp

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

<form method="GET" action="{{ $action }}" class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label class="block text-sm font-medium text-slate-700">
            Fecha desde
            <input type="date" name="fecha_desde" value="{{ old('fecha_desde', $filters['fecha_desde'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Fecha hasta
            <input type="date" name="fecha_hasta" value="{{ old('fecha_hasta', $filters['fecha_hasta'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        @if ($showDocument)
            <label class="block text-sm font-medium text-slate-700">
                Documento
                <input type="text" name="documento" maxlength="30" value="{{ old('documento', $filters['documento'] ?? '') }}" placeholder="Prefijo o valor completo" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-900">
            </label>
        @endif

        <label class="block text-sm font-medium text-slate-700">
            Operación
            <input type="text" name="operacion" maxlength="100" value="{{ old('operacion', $filters['operacion'] ?? '') }}" placeholder="Prefijo o valor completo" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Recaudo exacto
            <input type="text" name="recaudo" maxlength="50" value="{{ old('recaudo', $filters['recaudo'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Monto mínimo
            <input type="number" name="monto_min" min="0" step="0.01" value="{{ old('monto_min', $filters['monto_min'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        <label class="block text-sm font-medium text-slate-700">
            Monto máximo
            <input type="number" name="monto_max" min="0" step="0.01" value="{{ old('monto_max', $filters['monto_max'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>

        @if ($showStatus)
            <label class="block text-sm font-medium text-slate-700">
                Estado
                <select name="estado" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kp-500">
                    @foreach (['todos' => 'Todos', 'identificados' => 'Identificados', 'sin_identificar' => 'Sin identificar'] as $value => $label)
                        <option value="{{ $value }}" @selected(old('estado', $filters['estado'] ?? 'todos') === $value)>{{ $label }}</option>
                    @endforeach
                </select>
            </label>
        @endif

        <label class="block text-sm font-medium text-slate-700">
            Filas por página
            <select name="per_page" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kp-500">
                @foreach ([25, 50, 100] as $size)
                    <option value="{{ $size }}" @selected((int) old('per_page', $filters['per_page'] ?? 25) === $size)>{{ $size }}</option>
                @endforeach
            </select>
        </label>
    </div>

    <div class="mt-5 flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4">
        <button type="submit" class="rounded-lg bg-kp-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-kp-700">Buscar</button>
        <a href="{{ $action }}" class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Limpiar filtros</a>
    </div>
</form>
