@if ($errors->any())
    <div class="mb-3 rounded-control border border-red-300 bg-red-50 px-3 py-2 text-[13px] text-red-900" role="alert">
        <p class="font-semibold">Revisa los filtros ingresados.</p>
        <ul class="mt-2 list-disc space-y-1 pl-5">
            @foreach ($errors->all() as $error)
                <li>{{ $error }}</li>
            @endforeach
        </ul>
    </div>
@endif

@php
    $hasAdvancedFilters = filled($filters['tipo'] ?? null)
        || filled($filters['fecha_desde'] ?? null)
        || filled($filters['entidad'] ?? null)
        || filled($filters['fecha_hasta'] ?? null)
        || filled($filters['usuario'] ?? null)
        || (int) ($filters['per_page'] ?? 25) !== 25;
@endphp

<form method="GET" action="{{ route('imports.index') }}" class="kp-panel overflow-hidden">
    <div class="kp-section-header">
        <div class="flex items-center gap-2.5">
            <svg class="size-4 text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 5h18M6 12h12m-8 7h4"/></svg>
            <h3 class="text-sm font-semibold text-slate-900">Filtros de búsqueda</h3>
        </div>
        <a href="{{ route('imports.index') }}" class="text-xs font-semibold text-muted hover:text-primary">Limpiar</a>
    </div>

    <div class="p-3">
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label class="kp-label">
                N.º de carga
                <input type="number" name="batch_id" min="1" value="{{ old('batch_id', $filters['batch_id'] ?? '') }}" placeholder="Ej. 125" class="kp-field normal-case tracking-normal">
            </label>

            <label class="kp-label md:col-span-1 xl:col-span-1">
                Archivo
                <input type="text" name="nombre_archivo" maxlength="255" value="{{ old('nombre_archivo', $filters['nombre_archivo'] ?? '') }}" placeholder="Buscar por nombre" class="kp-field normal-case tracking-normal">
            </label>

            <label class="kp-label">
                Estado
                <select name="estado" class="kp-field normal-case tracking-normal">
                    <option value="">Todos los estados</option>
                    @foreach ($statuses as $status)
                        <option value="{{ $status->value }}" @selected(($filters['estado'] ?? '') === $status->value)>{{ $status->label() }}</option>
                    @endforeach
                </select>
            </label>

            <label class="kp-label">
                Origen
                <select name="origen" class="kp-field normal-case tracking-normal">
                    <option value="">Todos los orígenes</option>
                    @foreach ($origins as $origin)
                        <option value="{{ $origin->value }}" @selected(($filters['origen'] ?? '') === $origin->value)>{{ $origin->label() }}</option>
                    @endforeach
                </select>
            </label>
        </div>

        <details class="mt-3 border-t border-border pt-2.5" @if ($hasAdvancedFilters) open @endif>
            <summary class="flex cursor-pointer list-none items-center gap-2 text-xs font-semibold text-muted hover:text-primary">
                <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="m9 18 6-6-6-6"/></svg>
                Más filtros
            </summary>

            <div class="mt-3 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                <label class="kp-label">
                    Tipo
                    <select name="tipo" class="kp-field normal-case tracking-normal">
                        <option value="">Todos</option>
                        @foreach ($types as $type)
                            <option value="{{ $type->value }}" @selected(($filters['tipo'] ?? '') === $type->value)>{{ $type->label() }}</option>
                        @endforeach
                    </select>
                </label>

                <label class="kp-label">
                    Entidad
                    <select name="entidad" class="kp-field normal-case tracking-normal">
                        <option value="">Todas</option>
                        @foreach ($entities as $entity)
                            <option value="{{ $entity->value }}" @selected(($filters['entidad'] ?? '') === $entity->value)>{{ $entity->label() }}</option>
                        @endforeach
                    </select>
                </label>

                <label class="kp-label">
                    Desde
                    <input type="date" name="fecha_desde" value="{{ old('fecha_desde', $filters['fecha_desde'] ?? '') }}" class="kp-field normal-case tracking-normal">
                </label>

                <label class="kp-label">
                    Hasta
                    <input type="date" name="fecha_hasta" value="{{ old('fecha_hasta', $filters['fecha_hasta'] ?? '') }}" class="kp-field normal-case tracking-normal">
                </label>

                <label class="kp-label">
                    Usuario
                    <input type="text" name="usuario" maxlength="100" value="{{ old('usuario', $filters['usuario'] ?? '') }}" placeholder="Buscar por nombre" class="kp-field normal-case tracking-normal">
                </label>

                <label class="kp-label">
                    Resultados
                    <select name="per_page" class="kp-field normal-case tracking-normal">
                        @foreach ([25, 50, 100] as $size)
                            <option value="{{ $size }}" @selected((int) ($filters['per_page'] ?? 25) === $size)>{{ $size }} por página</option>
                        @endforeach
                    </select>
                </label>
            </div>
        </details>

        <div class="mt-3 flex justify-end">
            <button type="submit" class="kp-btn-primary">
                <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="11" cy="11" r="7" stroke-width="1.8"/><path stroke-linecap="round" stroke-width="1.8" d="m20 20-4-4"/></svg>
                Buscar cargas
            </button>
        </div>
    </div>
</form>
