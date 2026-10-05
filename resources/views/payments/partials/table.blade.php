@php
    $variant = $variant ?? 'all';
    $unidentified = $variant === 'unidentified';
    $columnCount = $unidentified ? 7 : 9;
@endphp

<div class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead class="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Fecha</th>
                    @unless ($unidentified)
                        <th scope="col" class="whitespace-nowrap px-4 py-3">Documento</th>
                    @endunless
                    <th scope="col" class="whitespace-nowrap px-4 py-3 text-right">Monto</th>
                    @unless ($unidentified)
                        <th scope="col" class="whitespace-nowrap px-4 py-3 text-right">Acumulado</th>
                    @endunless
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Recaudo</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Operación</th>
                    <th scope="col" class="min-w-64 px-4 py-3">Comentario</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Hora</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3 text-right">Acciones</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 bg-white text-slate-700">
                @forelse ($payments as $payment)
                    <tr class="hover:bg-slate-50/70">
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
                            <a href="{{ route('payments.show', $payment->raw_id) }}" class="inline-flex rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-kp-300 hover:bg-kp-50 hover:text-kp-700">Ver</a>
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="{{ $columnCount }}" class="px-6 py-14 text-center">
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
