@if ($errors->any())
    <div class="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
        <p class="font-semibold">No se pudo guardar el cambio.</p>
        <ul class="mt-2 list-disc space-y-1 pl-5">
            @foreach ($errors->all() as $error)
                <li>{{ $error }}</li>
            @endforeach
        </ul>
    </div>
@endif

<div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,0.8fr)]">
    <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div class="border-b border-slate-100 px-5 py-4">
            <h3 class="font-semibold text-slate-900">Información del pago</h3>
            <p class="mt-1 text-sm text-slate-500">Datos de referencia para confirmar la asociación.</p>
        </div>
        <dl class="grid sm:grid-cols-2">
            @foreach ([
                ['label' => 'Fecha', 'value' => $payment->FECHA ? \Illuminate\Support\Carbon::parse($payment->FECHA)->format('d/m/Y') : '—'],
                ['label' => 'Hora', 'value' => $payment->HORA ? substr((string) $payment->HORA, 0, 8) : '—', 'mono' => true],
                ['label' => 'Monto', 'value' => $payment->MONTO !== null ? 'S/ '.number_format((float) $payment->MONTO, 2, '.', ',') : '—'],
                ['label' => 'Recaudo', 'value' => filled($payment->RECAUDO) ? $payment->RECAUDO : '—'],
                ['label' => 'Operación', 'value' => filled($payment->OPERACION) ? $payment->OPERACION : '—', 'mono' => true],
            ] as $item)
                <div class="border-b border-slate-100 px-5 py-4 sm:border-r">
                    <dt class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ $item['label'] }}</dt>
                    <dd @class(['mt-1.5 break-words text-sm text-slate-900', 'font-mono' => $item['mono'] ?? false])>{{ $item['value'] }}</dd>
                </div>
            @endforeach
        </dl>
        <div class="px-5 py-4">
            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">Comentario</p>
            <p class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{{ filled($payment->COMENTARIO) ? $payment->COMENTARIO : 'Sin comentario' }}</p>
        </div>
    </section>

    <section class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        @if ($mode === 'correct')
            <div class="mb-5 rounded-xl bg-slate-50 px-4 py-3">
                <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">Documento actual</p>
                <p class="mt-1 font-mono text-lg font-semibold text-slate-900">{{ $payment->DOCUMENTO }}</p>
            </div>
        @endif

        <form method="POST" action="{{ $action }}" class="space-y-5">
            @csrf
            @if ($method !== 'POST')
                @method($method)
            @endif

            <label class="block text-sm font-medium text-slate-700">
                {{ $mode === 'correct' ? 'Nuevo documento' : 'Documento' }}
                <input type="text" name="documento" maxlength="30" required value="{{ old('documento') }}" autocomplete="off" class="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-sm text-slate-900" autofocus>
                <span class="mt-1 block text-xs font-normal text-slate-500">Se conservará exactamente el valor ingresado, sin homologarlo.</span>
            </label>

            <label class="block text-sm font-medium text-slate-700">
                Motivo
                <textarea name="motivo" maxlength="260" rows="5" required class="mt-1.5 w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900">{{ old('motivo') }}</textarea>
                <span class="mt-1 block text-xs font-normal text-slate-500">Máximo 260 caracteres. Este texto formará parte permanente de la auditoría.</span>
            </label>

            <div class="flex flex-wrap gap-3 border-t border-slate-100 pt-5">
                <button type="submit" class="rounded-lg bg-kp-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-kp-700">
                    {{ $mode === 'correct' ? 'Guardar corrección' : 'Guardar identificación' }}
                </button>
                <a href="{{ route('payments.show', $payment->raw_id) }}" class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Cancelar</a>
            </div>
        </form>
    </section>
</div>
