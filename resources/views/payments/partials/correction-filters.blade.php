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

<form method="GET" action="{{ route('payments.corrections') }}" class="kp-panel p-4 sm:p-5">
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <label class="block text-sm font-medium text-slate-700">
            Fecha cambio desde
            <input type="date" name="fecha_cambio_desde" value="{{ old('fecha_cambio_desde', $filters['fecha_cambio_desde'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>
        <label class="block text-sm font-medium text-slate-700">
            Fecha cambio hasta
            <input type="date" name="fecha_cambio_hasta" value="{{ old('fecha_cambio_hasta', $filters['fecha_cambio_hasta'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>
        <label class="block text-sm font-medium text-slate-700">
            Documento
            <input type="text" name="documento" maxlength="30" value="{{ old('documento', $filters['documento'] ?? '') }}" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-900">
        </label>
        <label class="block text-sm font-medium text-slate-700">
            Usuario
            <input type="text" name="usuario" maxlength="100" value="{{ old('usuario', $filters['usuario'] ?? '') }}" placeholder="Buscar por nombre" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">
        </label>
        <label class="block text-sm font-medium text-slate-700">
            Filas por página
            <select name="per_page" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kp-500">
                @foreach ([25, 50, 100] as $size)
                    <option value="{{ $size }}" @selected((int) old('per_page', $filters['per_page'] ?? 25) === $size)>{{ $size }}</option>
                @endforeach
            </select>
        </label>
    </div>
    <div class="mt-5 flex flex-wrap gap-3 border-t border-slate-100 pt-4">
        <button type="submit" class="kp-btn-primary !py-2">Buscar</button>
        <a href="{{ route('payments.corrections') }}" class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Limpiar filtros</a>
    </div>
</form>
