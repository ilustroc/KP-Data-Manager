@extends('layouts.app')

@section('title', 'Dashboard')
@section('page-heading', 'Dashboard')

@section('content')
    <div class="mx-auto max-w-7xl">
        <section class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
            <div class="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
                <div>
                    <p class="text-sm font-semibold text-kp-600">Fase 1 completada</p>
                    <h2 class="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Base segura para KP Data Manager</h2>
                    <p class="mt-3 max-w-2xl text-sm leading-6 text-slate-600">La autenticación, los roles, el layout administrativo y las conexiones por esquema están preparados. Los indicadores de pagos se habilitarán en la siguiente fase.</p>
                </div>
                <span class="inline-flex w-fit items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">
                    <span class="size-2 rounded-full bg-emerald-500"></span>
                    Aplicación operativa
                </span>
            </div>
        </section>

        <section class="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Módulos planificados">
            @foreach ([
                ['label' => 'Pagos', 'description' => 'Consulta y filtros', 'phase' => 'Fase 2'],
                ['label' => 'Identificación', 'description' => 'Corrección auditable', 'phase' => 'Fase 3'],
                ['label' => 'Cargas', 'description' => 'Control de importaciones', 'phase' => 'Fase 4'],
                ['label' => 'ETL', 'description' => 'Procesamiento masivo', 'phase' => 'Fase 5'],
            ] as $module)
                <article class="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div class="flex items-center justify-between gap-3">
                        <h3 class="font-semibold text-slate-900">{{ $module['label'] }}</h3>
                        <span class="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">{{ $module['phase'] }}</span>
                    </div>
                    <p class="mt-2 text-sm text-slate-500">{{ $module['description'] }}</p>
                </article>
            @endforeach
        </section>

        <section class="mt-6 grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
            <div class="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
                <div class="mx-auto grid size-12 place-items-center rounded-xl bg-slate-100 text-slate-500">
                    <svg class="size-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 19V9m5 10V5m5 14v-7m5 7V3"/></svg>
                </div>
                <h3 class="mt-4 font-semibold text-slate-900">Indicadores pendientes</h3>
                <p class="mt-2 text-sm text-slate-500">Los indicadores usarán consultas Silver optimizadas cuando se implemente el módulo de pagos.</p>
            </div>

            <aside class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <p class="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Sesión actual</p>
                <dl class="mt-4 flex flex-col gap-4 text-sm">
                    <div>
                        <dt class="text-slate-500">Usuario</dt>
                        <dd class="mt-1 font-medium text-slate-900">{{ auth()->user()->name }}</dd>
                    </div>
                    <div>
                        <dt class="text-slate-500">Rol</dt>
                        <dd class="mt-1 font-medium text-slate-900">{{ auth()->user()->role->label() }}</dd>
                    </div>
                </dl>
            </aside>
        </section>
    </div>
@endsection
