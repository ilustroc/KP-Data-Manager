<div class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
    <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead class="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Fecha</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Usuario</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Documento anterior</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Documento nuevo</th>
                    <th scope="col" class="min-w-64 px-4 py-3">Motivo</th>
                    <th scope="col" class="whitespace-nowrap px-4 py-3">Estado</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 bg-white text-slate-700">
                @forelse ($history as $resolution)
                    <tr>
                        <td class="whitespace-nowrap px-4 py-3"><x-utc-datetime :value="$resolution->fecha_modificacion" /></td>
                        <td class="whitespace-nowrap px-4 py-3 font-mono text-xs">{{ $resolution->usuario }}</td>
                        <td class="whitespace-nowrap px-4 py-3 font-mono">{{ filled($resolution->documento_anterior) ? $resolution->documento_anterior : '—' }}</td>
                        <td class="whitespace-nowrap px-4 py-3 font-mono font-medium text-slate-900">{{ $resolution->documento_nuevo }}</td>
                        <td class="max-w-lg whitespace-pre-wrap break-words px-4 py-3">{{ filled($resolution->motivo) ? $resolution->motivo : '—' }}</td>
                        <td class="whitespace-nowrap px-4 py-3">
                            @if ((bool) $resolution->activo)
                                <span class="inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">Vigente</span>
                            @else
                                <span class="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">Histórica</span>
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
