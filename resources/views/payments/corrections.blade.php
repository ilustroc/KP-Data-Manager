@extends('layouts.app')

@section('title', 'Correcciones de pagos')
@section('page-heading', 'Correcciones')

@section('content')
    <div class="mx-auto max-w-[100rem]">
        <div class="mb-6">
            <h2 class="text-2xl font-semibold tracking-tight text-slate-950">Correcciones</h2>
            <p class="mt-1 text-sm text-slate-600">Auditoría completa de identificaciones y cambios de documento.</p>
        </div>

        @include('payments.partials.correction-filters', ['filters' => $filters])

        <div class="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
                    <thead class="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                        <tr>
                            <th scope="col" class="whitespace-nowrap px-4 py-3">Fecha cambio</th>
                            <th scope="col" class="whitespace-nowrap px-4 py-3">Fecha pago</th>
                            <th scope="col" class="whitespace-nowrap px-4 py-3">Documento anterior</th>
                            <th scope="col" class="whitespace-nowrap px-4 py-3">Documento nuevo</th>
                            <th scope="col" class="whitespace-nowrap px-4 py-3 text-right">Monto</th>
                            <th scope="col" class="whitespace-nowrap px-4 py-3">Operación</th>
                            <th scope="col" class="whitespace-nowrap px-4 py-3">Usuario</th>
                            <th scope="col" class="min-w-64 px-4 py-3">Motivo</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100 bg-white text-slate-700">
                        @forelse ($corrections as $correction)
                            <tr>
                                <td class="whitespace-nowrap px-4 py-3"><x-utc-datetime :value="$correction->fecha_modificacion" /></td>
                                <td class="whitespace-nowrap px-4 py-3">{{ $correction->fecha_pago ? \Illuminate\Support\Carbon::parse($correction->fecha_pago)->format('d/m/Y') : '—' }}</td>
                                <td class="whitespace-nowrap px-4 py-3 font-mono">{{ filled($correction->documento_anterior) ? $correction->documento_anterior : '—' }}</td>
                                <td class="whitespace-nowrap px-4 py-3 font-mono font-medium text-slate-900">{{ $correction->documento_nuevo }}</td>
                                <td class="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-900">{{ $correction->MONTO !== null ? 'S/ '.number_format((float) $correction->MONTO, 2, '.', ',') : '—' }}</td>
                                <td class="whitespace-nowrap px-4 py-3 font-mono">{{ filled($correction->OPERACION) ? $correction->OPERACION : '—' }}</td>
                                <td class="whitespace-nowrap px-4 py-3 font-mono text-xs">{{ $correction->usuario }}</td>
                                <td class="max-w-lg whitespace-pre-wrap break-words px-4 py-3">{{ filled($correction->motivo) ? $correction->motivo : '—' }}</td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="8" class="px-6 py-12 text-center text-sm text-slate-500">No se encontraron correcciones con los filtros seleccionados.</td>
                            </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>

            @if ($corrections->hasPages())
                <div class="border-t border-slate-200 px-4 py-3 sm:px-5">
                    {{ $corrections->links() }}
                </div>
            @endif
        </div>
    </div>
@endsection
