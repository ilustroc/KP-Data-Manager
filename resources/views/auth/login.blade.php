@extends('layouts.guest')

@section('title', 'Iniciar sesión')

@section('content')
    <div class="rounded-panel border border-border bg-white p-6 sm:p-8">
        <img src="{{ asset('assets/brand/kp-invest-logo.png') }}" alt="KP Invest" class="h-10 w-auto">

        <div>
            <h2 class="mt-7 text-2xl font-semibold tracking-[-0.02em] text-ink">Bienvenido</h2>
            <p class="mt-2 text-sm leading-6 text-slate-500">Ingresa a KP Data Manager con tus credenciales.</p>
        </div>

        @if ($errors->any())
            <div class="mt-5 rounded-control border border-red-300 bg-red-50 px-3 py-2 text-[13px] text-red-700" role="alert">
                {{ $errors->first() }}
            </div>
        @endif

        <form class="mt-6 flex flex-col gap-4" method="POST" action="{{ route('login.store') }}">
            @csrf

            <div>
                <label for="email" class="text-sm font-medium text-slate-700">Correo electrónico</label>
                <input id="email" name="email" type="email" value="{{ old('email') }}" required autofocus autocomplete="username" class="mt-1.5 block h-10 w-full rounded-control border border-slate-300 bg-white px-3 text-[13px] text-ink placeholder:text-slate-400 focus:border-primary focus:ring-1 focus:ring-primary/20" placeholder="nombre@kpinvest.pe">
            </div>

            <div>
                <label for="password" class="text-sm font-medium text-slate-700">Contraseña</label>
                <div class="relative mt-2">
                    <input id="password" data-password-input name="password" type="password" required autocomplete="current-password" class="block h-10 w-full rounded-control border border-slate-300 bg-white px-3 pr-10 text-[13px] text-ink focus:border-primary focus:ring-1 focus:ring-primary/20">
                    <button data-password-toggle type="button" class="absolute inset-y-0 right-0 grid w-10 place-items-center rounded-r-control text-slate-500 hover:text-primary" aria-label="Mostrar contraseña" aria-controls="password">
                        <svg data-password-show-icon class="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.5" stroke-width="1.8"/></svg>
                        <svg data-password-hide-icon class="hidden size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="m3 3 18 18M10.6 6.2A9.8 9.8 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-2.1 2.8M6.2 6.2C3.8 8 2.5 12 2.5 12s3.5 6 9.5 6c1.3 0 2.5-.3 3.6-.7M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>
                    </button>
                </div>
            </div>

            <label class="flex items-center gap-2.5 text-sm text-slate-600">
                <input name="remember" type="checkbox" value="1" class="size-4 rounded-control border-slate-300 text-primary focus:ring-primary">
                Mantener sesión iniciada
            </label>

            <button type="submit" class="h-10 rounded-control bg-primary px-4 text-sm font-semibold text-white transition-colors hover:bg-primary-hover">
                Iniciar sesión
            </button>
        </form>
    </div>
@endsection
