@php
    $filters = $filters ?? [];
    $showDocument = $showDocument ?? true;
    $showStatus = $showStatus ?? true;
@endphp

@if ($errors->any())
    <div class="mb-3 rounded-control border border-red-300 bg-red-50 px-3 py-2 text-[13px] text-red-800" role="alert">
        <p class="font-semibold">Revisa los filtros ingresados.</p>
        <ul class="mt-2 list-disc space-y-1 pl-5">
            @foreach ($errors->all() as $error)
                <li>{{ $error }}</li>
            @endforeach
        </ul>
    </div>
@endif

<form method="GET" action="{{ $action }}" class="kp-panel p-3">
    <div class="grid gap-3 md:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-8">
        <label class="kp-label">
            Fecha desde
            <input type="date" name="fecha_desde" value="{{ old('fecha_desde', $filters['fecha_desde'] ?? '') }}" class="kp-field normal-case tracking-normal">
        </label>

        <label class="kp-label">
            Fecha hasta
            <input type="date" name="fecha_hasta" value="{{ old('fecha_hasta', $filters['fecha_hasta'] ?? '') }}" class="kp-field normal-case tracking-normal">
        </label>

        @if ($showDocument)
            <label class="kp-label">
                Documento
                <input type="text" name="documento" maxlength="30" value="{{ old('documento', $filters['documento'] ?? '') }}" placeholder="Prefijo o valor completo" class="kp-field font-mono normal-case tracking-normal">
            </label>
        @endif

        <label class="kp-label">
            Operación
            <input type="text" name="operacion" maxlength="100" value="{{ old('operacion', $filters['operacion'] ?? '') }}" placeholder="Prefijo o valor completo" class="kp-field font-mono normal-case tracking-normal">
        </label>

        <label class="kp-label">
            Recaudo exacto
            <input type="text" name="recaudo" maxlength="50" value="{{ old('recaudo', $filters['recaudo'] ?? '') }}" class="kp-field normal-case tracking-normal">
        </label>

        <label class="kp-label">
            Monto mínimo
            <input type="number" name="monto_min" min="0" step="0.01" value="{{ old('monto_min', $filters['monto_min'] ?? '') }}" class="kp-field normal-case tracking-normal">
        </label>

        <label class="kp-label">
            Monto máximo
            <input type="number" name="monto_max" min="0" step="0.01" value="{{ old('monto_max', $filters['monto_max'] ?? '') }}" class="kp-field normal-case tracking-normal">
        </label>

        @if ($showStatus)
            <label class="kp-label">
                Estado
                <select name="estado" class="kp-field normal-case tracking-normal">
                    @foreach (['todos' => 'Todos', 'identificados' => 'Identificados', 'sin_identificar' => 'Sin identificar'] as $value => $label)
                        <option value="{{ $value }}" @selected(old('estado', $filters['estado'] ?? 'todos') === $value)>{{ $label }}</option>
                    @endforeach
                </select>
            </label>
        @endif

        <label class="kp-label">
            Filas por página
            <select name="per_page" class="kp-field normal-case tracking-normal">
                @foreach ([25, 50, 100] as $size)
                    <option value="{{ $size }}" @selected((int) old('per_page', $filters['per_page'] ?? 25) === $size)>{{ $size }}</option>
                @endforeach
            </select>
        </label>
    </div>

    <div class="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <button type="submit" class="kp-btn-primary">Buscar</button>
        <a href="{{ $action }}" class="kp-btn-secondary">Limpiar filtros</a>
    </div>
</form>
