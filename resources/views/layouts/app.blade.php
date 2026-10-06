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
    <div class="min-h-screen lg:flex">
        <div data-sidebar-overlay class="fixed inset-0 z-30 hidden bg-slate-950/55 backdrop-blur-[1px] lg:hidden"></div>

        <aside data-sidebar class="fixed inset-y-0 left-0 z-40 flex w-64 -translate-x-full flex-col bg-sidebar text-white shadow-2xl transition-transform duration-200 lg:static lg:translate-x-0 lg:shadow-none">
            <div class="flex h-[5rem] items-center border-b border-white/10 px-4">
                <div class="flex w-full items-center gap-3 rounded-lg bg-white px-3 py-2 shadow-sm">
                    <img src="{{ asset('assets/brand/kp-invest-logo.png') }}" alt="KP Invest" class="h-7 w-auto shrink-0">
                    <span class="border-l border-slate-200 pl-3 text-[10px] font-bold uppercase leading-4 tracking-[0.12em] text-brand-blue">Data<br>Manager</span>
                </div>
            </div>

            <nav class="flex-1 overflow-y-auto px-3 py-5" aria-label="Navegación principal">
                <div class="flex flex-col gap-1">
                    <x-sidebar-link :href="route('dashboard')" :active="request()->routeIs('dashboard')">
                        <x-slot:icon>
                            <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M3 13h8V3H3v10Zm0 8h8v-4H3v4Zm12 0h6V11h-6v10Zm0-14h6V3h-6v4Z"/></svg>
                        </x-slot:icon>
                        Dashboard
                    </x-sidebar-link>
                </div>

                <div class="mt-8">
                    <p class="px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">Cargas</p>
                    <div class="mt-2 flex flex-col gap-1">
                        @can('operate')
                            <x-sidebar-link :href="route('imports.create')" :active="request()->routeIs('imports.create')">
                                <x-slot:icon>
                                    <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4"/></svg>
                                </x-slot:icon>
                                Nueva carga
                            </x-sidebar-link>
                        @endcan
                        <x-sidebar-link :href="route('imports.index')" :active="request()->routeIs('imports.index', 'imports.show')">
                            <x-slot:icon>
                                <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8v4l3 2m6-2a9 9 0 1 1-3-6.7M21 4v5h-5"/></svg>
                            </x-slot:icon>
                            Historial
                        </x-sidebar-link>
                    </div>
                </div>

                <div class="mt-8">
                    <p class="px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">Pagos</p>
                    <div class="mt-2 flex flex-col gap-1">
                        <x-sidebar-link :href="route('payments.index')" :active="request()->routeIs('payments.index')">
                            <x-slot:icon>
                                <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6h16M4 12h16M4 18h10"/></svg>
                            </x-slot:icon>
                            Todos
                        </x-sidebar-link>
                        <x-sidebar-link :href="route('payments.unidentified')" :active="request()->routeIs('payments.unidentified')">
                            <x-slot:icon>
                                <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 8v5m0 3h.01M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/></svg>
                            </x-slot:icon>
                            Sin identificar
                        </x-sidebar-link>
                        <x-sidebar-link :href="route('payments.corrections')" :active="request()->routeIs('payments.corrections')">
                            <x-slot:icon>
                                <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M16.9 4.1a2.1 2.1 0 0 1 3 3L9 18l-4 1 1-4L16.9 4.1Z"/></svg>
                            </x-slot:icon>
                            Correcciones
                        </x-sidebar-link>
                    </div>
                </div>
            </nav>

            <div class="border-t border-white/8 p-3">
                <div class="mb-2 flex items-center gap-3 rounded-lg bg-white/[0.04] px-3 py-2.5">
                    <div class="min-w-0 flex-1">
                        <p class="truncate text-sm font-medium" title="{{ auth()->user()->name }}">{{ auth()->user()->name }}</p>
                        <p class="truncate text-xs text-slate-400">{{ auth()->user()->role->label() }}</p>
                    </div>
                </div>
                <form method="POST" action="{{ route('logout') }}">
                    @csrf
                    <button type="submit" class="w-full rounded-lg px-3 py-2 text-left text-xs font-medium text-slate-400 transition-colors hover:bg-white/5 hover:text-white">
                        Cerrar sesión
                    </button>
                </form>
            </div>
        </aside>

        <div class="min-w-0 flex-1">
            <header class="sticky top-0 z-20 flex h-[4.5rem] items-center justify-between border-b border-slate-200/90 bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
                <div class="flex items-center gap-3">
                    <button data-sidebar-toggle type="button" class="rounded-lg border border-slate-300 bg-white p-2 text-slate-600 lg:hidden" aria-label="Abrir navegación" aria-expanded="false">
                        <svg class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-width="2" d="M4 7h16M4 12h16M4 17h16"/></svg>
                    </button>
                    <div>
                        <p class="text-[10px] font-bold uppercase tracking-[0.18em] text-kp-600">KP INVEST</p>
                        <h1 class="text-base font-semibold text-slate-950 sm:text-lg">@yield('page-heading', 'Dashboard')</h1>
                    </div>
                </div>
            </header>

            <main class="min-h-[calc(100vh-4.5rem)] p-4 sm:p-6 lg:p-8">
                @if (session('status'))
                    <div class="mx-auto mb-5 flex max-w-[100rem] items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900" role="status">
                        <svg class="mt-0.5 size-4 shrink-0 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m5 12 4 4L19 6"/></svg>
                        <span class="font-medium">{{ session('status') }}</span>
                    </div>
                @endif
                @if (session('warning'))
                    <div class="mx-auto mb-5 flex max-w-[100rem] items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950" role="status">
                        <svg class="mt-0.5 size-4 shrink-0 text-amber-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v4m0 4h.01M10.3 3.8 2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.8a2 2 0 0 0-3.4 0Z"/></svg>
                        <span class="font-medium">{{ session('warning') }}</span>
                    </div>
                @endif
                @yield('content')
            </main>
        </div>
    </div>
</body>
</html>
