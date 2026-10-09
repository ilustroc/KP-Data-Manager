@php
    $variant = $variant ?? 'all';
    $unidentified = $variant === 'unidentified';
    $columnCount = $unidentified ? 7 : 9;
@endphp

<div class="kp-panel overflow-hidden">
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-border text-left text-[13px]">
            <thead class="bg-slate-100/80 text-[11px] font-semibold uppercase tracking-wide text-muted">
                <tr>
                    <th scope="col" class="kp-table-heading">Fecha</th>
                    @unless ($unidentified)
                        <th scope="col" class="kp-table-heading">Documento</th>
                    @endunless
                    <th scope="col" class="kp-table-heading text-right">Monto</th>
                    @unless ($unidentified)
                        <th scope="col" class="kp-table-heading text-right">Acumulado</th>
                    @endunless
                    <th scope="col" class="kp-table-heading">Recaudo</th>
                    <th scope="col" class="kp-table-heading">Operación</th>
                    <th scope="col" class="kp-table-heading min-w-64">Comentario</th>
                    <th scope="col" class="kp-table-heading">Hora</th>
                    <th scope="col" class="kp-table-heading text-right">Acciones</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-border bg-white text-slate-700">
                @forelse ($payments as $payment)
                    <tr class="hover:bg-blue-50/30">
                        <td class="whitespace-nowrap px-4 py-3">{{ $payment->FECHA ? \Illuminate\Support\Carbon::parse($payment->FECHA)->format('d/m/Y') : '—' }}</td>
                        @unless ($unidentified)
                            <td class="whitespace-nowrap px-4 py-3 font-mono text-slate-900">{{ filled($payment->DOCUMENTO) ? $payment->DOCUMENTO : '—' }}</td>
                        @endunless
                        <td class="whitespace-nowrap px-4 py-3 text-right font-medium text-slate-900">{{ $payment->MONTO !== null ? 'S/ '.number_format((float) $payment->MONTO, 2, '.', ',') : '—' }}</td>
                        @unless ($unidentified)
                            <td class="whitespace-nowrap px-4 py-3 text-right">{{ $payment->ACUMULADO !== null ? 'S/ '.number_format((float) $payment->ACUMULADO, 2, '.', ',') : '—' }}</td>
                        @endunless
                        <td class="whitespace-nowrap px-4 py-3">{{ filled($payment->RECAUDO) ? $payment->RECAUDO : '—' }}</td>
                        <td class="whitespace-nowrap px-4 py-3 font-mono text-slate-900">{{ filled($payment->OPERACION) ? $payment->OPERACION : '—' }}</td>
                        <td class="max-w-sm px-4 py-3 text-slate-600" title="{{ $payment->COMENTARIO }}">{{ filled($payment->COMENTARIO) ? \Illuminate\Support\Str::limit($payment->COMENTARIO, 80) : '—' }}</td>
                        <td class="whitespace-nowrap px-4 py-3 font-mono text-xs">{{ $payment->HORA ? substr((string) $payment->HORA, 0, 8) : '—' }}</td>
                        <td class="whitespace-nowrap px-4 py-3 text-right">
                            <div class="flex justify-end gap-2">
                                <a href="{{ route('payments.show', $payment->raw_id) }}" class="inline-flex h-7 items-center rounded-control border border-slate-300 px-2 text-xs font-semibold text-slate-700 hover:border-primary hover:bg-blue-50 hover:text-primary">Ver</a>
                                @can('operate')
                                    @if ($unidentified || blank($payment->DOCUMENTO))
                                        <a href="{{ route('payments.identify.create', $payment->raw_id) }}" class="inline-flex h-7 items-center rounded-control bg-primary px-2 text-xs font-semibold text-white hover:bg-primary-hover">Identificar</a>
                                    @else
                                        <a href="{{ route('payments.edit-document', $payment->raw_id) }}" class="inline-flex h-7 items-center rounded-control bg-primary px-2 text-xs font-semibold text-white hover:bg-primary-hover">Corregir</a>
                                    @endif
                                @endcan
                            </div>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="{{ $columnCount }}" class="px-6 py-8 text-center">
                            <p class="font-medium text-slate-700">No se encontraron pagos con los filtros seleccionados.</p>
                            <p class="mt-1 text-sm text-slate-500">Ajusta los criterios de búsqueda e inténtalo nuevamente.</p>
                        </td>
                    </tr>
                @endforelse
            </tbody>
        </table>
    </div>

    @if ($payments->hasPages())
        <div class="border-t border-slate-200 px-4 py-3 sm:px-5">
            {{ $payments->links() }}
        </div>
    @endif
</div>
