<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'Dashboard') · {{ config('app.name') }}</title>
    <link rel="icon" type="image/png" href="{{ asset('assets/brand/kp-invest-mark.png') }}">
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body>
    <div class="min-h-screen bg-workspace">
        <header class="sticky top-0 z-50 flex h-12 items-center justify-between bg-topbar px-3 text-white" aria-label="Barra principal">
            <div class="flex min-w-0 items-center gap-2.5">
                <button data-sidebar-toggle type="button" class="grid size-8 shrink-0 place-items-center rounded-control text-blue-100 hover:bg-white/10 hover:text-white lg:hidden" aria-label="Abrir navegación" aria-expanded="false">
                    <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-width="2" d="M4 7h16M4 12h16M4 17h16"/></svg>
                </button>
                <img src="{{ asset('assets/brand/kp-invest-logo.png') }}" alt="KP Invest" class="h-7 w-auto shrink-0 rounded-control bg-white px-1.5 py-1">
                <span class="truncate text-sm font-semibold tracking-[0.01em]">KP Data Manager</span>
                <span class="hidden h-4 w-px bg-white/25 sm:block" aria-hidden="true"></span>
                <span class="hidden truncate text-xs text-blue-100 sm:block">@yield('page-heading', 'Dashboard')</span>
            </div>

            <div class="flex items-center gap-2">
                <div class="hidden min-w-0 text-right sm:block">
                    <p class="max-w-56 truncate text-xs font-semibold" title="{{ auth()->user()->name }}">{{ auth()->user()->name }}</p>
                    <p class="text-[10px] uppercase tracking-wide text-blue-200">{{ auth()->user()->role->label() }}</p>
                </div>
                <form method="POST" action="{{ route('logout') }}">
                    @csrf
                    <button type="submit" class="grid size-8 place-items-center rounded-control text-blue-100 hover:bg-white/10 hover:text-white" aria-label="Cerrar sesión" title="Cerrar sesión">
                        <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M14 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-3m-4-4h11m0 0-3-3m3 3-3 3"/></svg>
                    </button>
                </form>
            </div>
        </header>

        <div class="flex min-h-[calc(100vh-var(--topbar-height))]">
            <div data-sidebar-overlay class="fixed inset-x-0 top-12 bottom-0 z-30 hidden bg-slate-950/45 lg:hidden"></div>

            <aside data-sidebar class="fixed top-12 bottom-0 left-0 z-40 flex w-60 -translate-x-full flex-col border-r border-border bg-sidebar transition-transform duration-150 lg:sticky lg:top-12 lg:h-[calc(100vh-var(--topbar-height))] lg:w-[var(--rail-width)] lg:translate-x-0" aria-label="Navegación principal">
                <nav class="flex-1 overflow-y-auto py-2">
                    <x-sidebar-link :href="route('dashboard')" :active="request()->routeIs('dashboard')">
                        <x-slot:icon><svg class="size-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 13h8V3H3v10Zm0 8h8v-4H3v4Zm12 0h6V11h-6v10Zm0-14h6V3h-6v4Z"/></svg></x-slot:icon>
                        Dashboard
                    </x-sidebar-link>

                    <div class="mx-2 my-2 border-t border-border" aria-hidden="true"></div>
                    <p class="px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 lg:sr-only">Cargas</p>
                    @can('operate')
                        <x-sidebar-link :href="route('imports.create')" :active="request()->routeIs('imports.create')">
                            <x-slot:icon><svg class="size-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4"/></svg></x-slot:icon>
                            Nueva carga
                        </x-sidebar-link>
                    @endcan
                    <x-sidebar-link :href="route('imports.index')" :active="request()->routeIs('imports.index', 'imports.show')">
                        <x-slot:icon><svg class="size-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8v4l3 2m6-2a9 9 0 1 1-3-6.7M21 4v5h-5"/></svg></x-slot:icon>
                        Historial de cargas
                    </x-sidebar-link>

                    <div class="mx-2 my-2 border-t border-border" aria-hidden="true"></div>
                    <p class="px-3 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 lg:sr-only">Pagos</p>
                    <x-sidebar-link :href="route('payments.index')" :active="request()->routeIs('payments.index')">
                        <x-slot:icon><svg class="size-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6h16M4 12h16M4 18h10"/></svg></x-slot:icon>
                        Todos los pagos
                    </x-sidebar-link>
                    <x-sidebar-link :href="route('payments.unidentified')" :active="request()->routeIs('payments.unidentified')">
                        <x-slot:icon><svg class="size-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8v5m0 3h.01M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/></svg></x-slot:icon>
                        Sin identificar
                    </x-sidebar-link>
                    <x-sidebar-link :href="route('payments.corrections')" :active="request()->routeIs('payments.corrections')">
                        <x-slot:icon><svg class="size-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M16.9 4.1a2.1 2.1 0 0 1 3 3L9 18l-4 1 1-4L16.9 4.1Z"/></svg></x-slot:icon>
                        Correcciones
                    </x-sidebar-link>
                </nav>

                <div class="border-t border-border p-2 lg:hidden">
                    <p class="truncate px-2 text-xs font-semibold text-slate-800" title="{{ auth()->user()->name }}">{{ auth()->user()->name }}</p>
                    <p class="px-2 text-[10px] uppercase tracking-wide text-muted">{{ auth()->user()->role->label() }}</p>
                </div>
            </aside>

            <main class="min-w-0 flex-1 p-3 sm:p-4 lg:p-5">
                @if (session('status'))
                    <div class="kp-alert kp-alert-success kp-page-shell mb-3" role="status">
                        <svg class="size-4 shrink-0 text-emerald-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m5 12 4 4L19 6"/></svg>
                        <span class="font-medium">{{ session('status') }}</span>
                    </div>
                @endif
                @if (session('warning'))
                    <div class="kp-alert kp-alert-warning kp-page-shell mb-3" role="status">
                        <svg class="size-4 shrink-0 text-amber-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v4m0 4h.01M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/></svg>
                        <span class="font-medium">{{ session('warning') }}</span>
                    </div>
                @endif
                @yield('content')
            </main>
        </div>
    </div>
</body>
</html>
