@if ($errors->any())
    <div class="mb-3 rounded-control border border-red-300 bg-red-50 px-3 py-2 text-[13px] text-red-800" role="alert">
        <p class="font-semibold">No se pudo guardar el cambio.</p>
        <ul class="mt-2 list-disc space-y-1 pl-5">
            @foreach ($errors->all() as $error)
                <li>{{ $error }}</li>
            @endforeach
        </ul>
    </div>
@endif

<div class="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
    <section class="kp-panel overflow-hidden">
        <div class="kp-section-header block">
            <h3 class="text-[13px] font-semibold text-ink">Información del pago</h3>
            <p class="text-[11px] text-muted">Datos de referencia para confirmar la asociación.</p>
        </div>
        <dl class="grid sm:grid-cols-2">
            @foreach ([
                ['label' => 'Fecha', 'value' => $payment->FECHA ? \Illuminate\Support\Carbon::parse($payment->FECHA)->format('d/m/Y') : '—'],
                ['label' => 'Hora', 'value' => $payment->HORA ? substr((string) $payment->HORA, 0, 8) : '—', 'mono' => true],
                ['label' => 'Monto', 'value' => $payment->MONTO !== null ? 'S/ '.number_format((float) $payment->MONTO, 2, '.', ',') : '—'],
                ['label' => 'Recaudo', 'value' => filled($payment->RECAUDO) ? $payment->RECAUDO : '—'],
                ['label' => 'Operación', 'value' => filled($payment->OPERACION) ? $payment->OPERACION : '—', 'mono' => true],
            ] as $item)
                <div class="border-b border-border px-4 py-3 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ $item['label'] }}</dt>
                    <dd @class(['mt-1.5 break-words text-sm text-slate-900', 'font-mono' => $item['mono'] ?? false])>{{ $item['value'] }}</dd>
                </div>
            @endforeach
        </dl>
        <div class="px-4 py-3">
            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">Comentario</p>
            <p class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{{ filled($payment->COMENTARIO) ? $payment->COMENTARIO : 'Sin comentario' }}</p>
        </div>
    </section>

    <section class="kp-panel p-4">
        @if ($mode === 'correct')
            <div class="mb-4 rounded-control border border-border bg-slate-50 px-3 py-2">
                <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">Documento actual</p>
                <p class="mt-1 font-mono text-lg font-semibold text-slate-900">{{ $payment->DOCUMENTO }}</p>
            </div>
        @endif

        <form method="POST" action="{{ $action }}" class="space-y-4">
            @csrf
            @if ($method !== 'POST')
                @method($method)
            @endif

            <label class="kp-label">
                {{ $mode === 'correct' ? 'Nuevo documento' : 'Documento' }}
                <input type="text" name="documento" maxlength="30" required value="{{ old('documento') }}" autocomplete="off" class="kp-field font-mono normal-case tracking-normal" autofocus>
                <span class="mt-1 block text-xs font-normal text-slate-500">Se conservará exactamente el valor ingresado, sin homologarlo.</span>
            </label>

            <label class="kp-label">
                Motivo
                <textarea name="motivo" maxlength="260" rows="5" required class="kp-field resize-y normal-case tracking-normal">{{ old('motivo') }}</textarea>
                <span class="mt-1 block text-xs font-normal text-slate-500">Máximo 260 caracteres. Este texto formará parte permanente de la auditoría.</span>
            </label>

            <div class="flex flex-wrap gap-2 border-t border-border pt-3">
                <button type="submit" class="kp-btn-primary">
                    {{ $mode === 'correct' ? 'Guardar corrección' : 'Guardar identificación' }}
                </button>
                <a href="{{ route('payments.show', $payment->raw_id) }}" class="kp-btn-secondary">Cancelar</a>
            </div>
        </form>
    </section>
</div>
