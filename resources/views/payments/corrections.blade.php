@extends('layouts.app')

@section('title', 'Correcciones de pagos')
@section('page-heading', 'Correcciones')

@section('content')
    <div class="kp-page-shell">
        <x-page-header title="Correcciones" subtitle="Auditoría completa de identificaciones y cambios de documento." />

        @include('payments.partials.correction-filters', ['filters' => $filters])

        <div class="kp-panel mt-3 overflow-hidden">
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-border text-left text-[13px]">
                    <thead class="bg-slate-100/80 text-[11px] font-semibold uppercase tracking-wide text-muted">
                        <tr>
                            <th scope="col" class="kp-table-heading">Fecha cambio</th>
                            <th scope="col" class="kp-table-heading">Fecha pago</th>
                            <th scope="col" class="kp-table-heading">Documento anterior</th>
                            <th scope="col" class="kp-table-heading">Documento nuevo</th>
                            <th scope="col" class="kp-table-heading text-right">Monto</th>
                            <th scope="col" class="kp-table-heading">Operación</th>
                            <th scope="col" class="kp-table-heading">Usuario</th>
                            <th scope="col" class="kp-table-heading min-w-64">Motivo</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-border bg-white text-slate-700">
                        @forelse ($corrections as $correction)
                            <tr class="hover:bg-blue-50/30">
                                <td class="whitespace-nowrap px-4 py-3"><x-utc-datetime :value="$correction->fecha_modificacion" /></td>
                                <td class="whitespace-nowrap px-4 py-3">{{ $correction->fecha_pago ? \Illuminate\Support\Carbon::parse($correction->fecha_pago)->format('d/m/Y') : '—' }}</td>
                                <td class="whitespace-nowrap px-4 py-3 font-mono">{{ filled($correction->documento_anterior) ? $correction->documento_anterior : '—' }}</td>
                                <td class="whitespace-nowrap px-4 py-3 font-mono font-medium text-slate-900">{{ $correction->documento_nuevo }}</td>
                                <td class="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-900">{{ $correction->MONTO !== null ? 'S/ '.number_format((float) $correction->MONTO, 2, '.', ',') : '—' }}</td>
                                <td class="whitespace-nowrap px-4 py-3 font-mono">{{ filled($correction->OPERACION) ? $correction->OPERACION : '—' }}</td>
                                <td class="max-w-52 px-4 py-3 text-sm font-medium text-slate-800"><span class="line-clamp-2" title="{{ $correction->usuario_nombre }}">{{ $correction->usuario_nombre }}</span></td>
                                <td class="max-w-sm whitespace-pre-wrap break-words px-4 py-3 leading-5">{{ filled($correction->motivo) ? $correction->motivo : '—' }}</td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="8" class="px-6 py-8 text-center text-[13px] text-muted">No se encontraron correcciones con los filtros seleccionados.</td>
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
