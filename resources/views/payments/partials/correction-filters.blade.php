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

<form method="GET" action="{{ route('payments.corrections') }}" class="kp-panel p-3">
    <div class="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        <label class="kp-label">
            Fecha cambio desde
            <input type="date" name="fecha_cambio_desde" value="{{ old('fecha_cambio_desde', $filters['fecha_cambio_desde'] ?? '') }}" class="kp-field normal-case tracking-normal">
        </label>
        <label class="kp-label">
            Fecha cambio hasta
            <input type="date" name="fecha_cambio_hasta" value="{{ old('fecha_cambio_hasta', $filters['fecha_cambio_hasta'] ?? '') }}" class="kp-field normal-case tracking-normal">
        </label>
        <label class="kp-label">
            Documento
            <input type="text" name="documento" maxlength="30" value="{{ old('documento', $filters['documento'] ?? '') }}" class="kp-field font-mono normal-case tracking-normal">
        </label>
        <label class="kp-label">
            Usuario
            <input type="text" name="usuario" maxlength="100" value="{{ old('usuario', $filters['usuario'] ?? '') }}" placeholder="Buscar por nombre" class="kp-field normal-case tracking-normal">
        </label>
        <label class="kp-label">
            Filas por página
            <select name="per_page" class="kp-field normal-case tracking-normal">
                @foreach ([25, 50, 100] as $size)
                    <option value="{{ $size }}" @selected((int) old('per_page', $filters['per_page'] ?? 25) === $size)>{{ $size }}</option>
                @endforeach
            </select>
        </label>
    </div>
    <div class="mt-3 flex flex-wrap gap-2 border-t border-border pt-3">
        <button type="submit" class="kp-btn-primary">Buscar</button>
        <a href="{{ route('payments.corrections') }}" class="kp-btn-secondary">Limpiar filtros</a>
    </div>
</form>
