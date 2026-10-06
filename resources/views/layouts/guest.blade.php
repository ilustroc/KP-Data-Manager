<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'Acceso') · {{ config('app.name') }}</title>
    <link rel="icon" type="image/png" href="{{ asset('assets/brand/kp-invest-mark.png') }}">
    @vite(['resources/css/app.css', 'resources/js/app.js'])
</head>
<body class="bg-[#f3f6f8]">
<main class="flex min-h-screen items-center justify-center p-5">
    <div class="grid w-full max-w-[80rem] overflow-hidden rounded-[20px] border border-slate-200 bg-white shadow-[0_20px_60px_rgba(6,27,69,0.08)] lg:h-[600px] lg:grid-cols-[1.08fr_.92fr]">
        <section class="relative hidden p-8 lg:flex lg:flex-col">
            <img src="{{ asset('assets/brand/kp-invest-logo.png') }}" alt="KP Invest" class="h-10 w-auto self-start">
            <div class="flex flex-1 flex-col items-center justify-center text-center">
                <img src="{{ asset('assets/brand/login-illustration.png') }}" alt="Persona gestionando información desde una computadora" class="max-h-[18rem] max-w-[70%] object-contain">
                <h1 class="mt-6 text-lg font-semibold text-brand-blue">Bienvenido a KP Invest</h1>
                <p class="mt-2 text-sm text-slate-500">Plataforma de KP Invest · Data Management</p>
            </div>
            <p class="text-xs text-slate-400">© {{ now()->year }} KP Invest · Acceso exclusivo para personal autorizado.</p>
        </section>
        <section class="flex min-h-screen items-center justify-center px-8 py-7 lg:min-h-0 lg:border-l lg:border-slate-100 lg:bg-slate-50/30">
            <div class="w-full max-w-[520px]">@yield('content')</div>
        </section>
    </div>
</main>
</body>
</html>