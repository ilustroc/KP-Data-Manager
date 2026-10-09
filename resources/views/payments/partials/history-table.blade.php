<div class="kp-panel overflow-hidden">
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-border text-left text-[13px]">
            <thead class="bg-slate-100/80 text-[11px] font-semibold uppercase tracking-wide text-muted">
                <tr>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Fecha</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Usuario</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Documento anterior</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Documento nuevo</th>
                    <th scope="col" class="min-w-64 px-4 py-3">Motivo</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Estado</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-border bg-white text-slate-700">
                @forelse ($history as $resolution)
                    <tr class="hover:bg-blue-50/30">
                        <td class="whitespace-nowrap px-4 py-3"><x-utc-datetime :value="$resolution->fecha_modificacion" /></td>
                        <td class="max-w-52 px-4 py-3 text-sm font-medium text-slate-800"><span class="line-clamp-2" title="{{ $resolution->usuario_nombre }}">{{ $resolution->usuario_nombre }}</span></td>
                        <td class="whitespace-nowrap px-4 py-3 font-mono">{{ filled($resolution->documento_anterior) ? $resolution->documento_anterior : '—' }}</td>
                        <td class="whitespace-nowrap px-4 py-3 font-mono font-medium text-slate-900">{{ $resolution->documento_nuevo }}</td>
                        <td class="max-w-lg whitespace-pre-wrap break-words px-4 py-3">{{ filled($resolution->motivo) ? $resolution->motivo : '—' }}</td>
                        <td class="whitespace-nowrap px-4 py-3">
                            @if ((bool) $resolution->activo)
                                <span class="inline-flex rounded-control border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">Vigente</span>
                            @else
                                <span class="inline-flex rounded-control border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">Histórica</span>
                            @endif
                        </td>
                    </tr>
                @empty
                    <tr>
                        <td colspan="6" class="px-6 py-10 text-center text-sm text-slate-500">Este pago todavía no tiene cambios de asociación registrados.</td>
                    </tr>
                @endforelse
            </tbody>
        </table>
    </div>
</div>
