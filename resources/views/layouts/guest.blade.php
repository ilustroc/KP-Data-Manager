<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'Acceso') · {{ config('app.name') }}</title>
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body>
    <main class="grid min-h-screen bg-slate-100 lg:grid-cols-[minmax(0,1fr)_minmax(28rem,40rem)]">
        <section class="hidden bg-sidebar p-12 text-white lg:flex lg:flex-col lg:justify-between">
            <div class="flex items-center gap-3">
                <div class="grid size-11 place-items-center rounded-xl bg-kp-500 text-sm font-black">KP</div>
                <div>
                    <p class="font-semibold">KP INVEST</p>
                    <p class="text-sm text-slate-400">Gestión interna de datos</p>
                </div>
            </div>
            <div class="max-w-xl">
                <p class="text-sm font-semibold uppercase tracking-[0.18em] text-blue-300">KP Data Manager</p>
                <h1 class="mt-4 text-4xl font-semibold leading-tight tracking-tight">Datos confiables, trazables y listos para operar.</h1>
                <p class="mt-5 max-w-lg text-base leading-7 text-slate-400">Plataforma interna para controlar cargas, pagos y correcciones con auditoría completa.</p>
            </div>
            <p class="text-xs text-slate-500">Acceso exclusivo para personal autorizado.</p>
        </section>

        <section class="flex items-center justify-center p-6 sm:p-10">
            <div class="w-full max-w-md">
                <div class="mb-8 flex items-center gap-3 lg:hidden">
                    <div class="grid size-10 place-items-center rounded-xl bg-kp-600 text-sm font-black text-white">KP</div>
                    <p class="font-semibold text-slate-900">KP Data Manager</p>
                </div>
                @yield('content')
            </div>
        </section>
    </main>
</body>
</html>
