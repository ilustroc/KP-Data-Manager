@extends('layouts.guest')

@section('title', 'Iniciar sesión')

@section('content')
    <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div>
            <p class="text-sm font-semibold text-kp-600">Bienvenido</p>
            <h2 class="mt-1 text-2xl font-semibold tracking-tight text-slate-950">Inicia sesión</h2>
            <p class="mt-2 text-sm leading-6 text-slate-500">Usa las credenciales asignadas por el administrador.</p>
        </div>

        @if ($errors->any())
            <div class="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
                {{ $errors->first() }}
            </div>
        @endif

        <form class="mt-7 flex flex-col gap-5" method="POST" action="{{ route('login.store') }}">
            @csrf

            <div>
                <label for="email" class="text-sm font-medium text-slate-700">Correo electrónico</label>
                <input id="email" name="email" type="email" value="{{ old('email') }}" required autofocus autocomplete="username" class="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-kp-500 focus:ring-3 focus:ring-kp-100" placeholder="nombre@kpinvest.pe">
            </div>

            <div>
                <label for="password" class="text-sm font-medium text-slate-700">Contraseña</label>
                <input id="password" name="password" type="password" required autocomplete="current-password" class="mt-2 block w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm focus:border-kp-500 focus:ring-3 focus:ring-kp-100">
            </div>

            <label class="flex items-center gap-2.5 text-sm text-slate-600">
                <input name="remember" type="checkbox" value="1" class="size-4 rounded border-slate-300 text-kp-600 focus:ring-kp-500">
                Mantener sesión iniciada
            </label>

            <button type="submit" class="rounded-lg bg-kp-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-kp-700">
                Ingresar
            </button>
        </form>
    </div>
@endsection
