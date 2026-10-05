<?php

namespace App\Http\Controllers;

use App\Http\Requests\Payments\PaymentDocumentRequest;
use App\Services\Payments\PaymentQueryService;
use App\Services\Payments\PaymentResolutionService;
use Illuminate\Http\RedirectResponse;
use Illuminate\View\View;

class PaymentDocumentController extends Controller
{
    public function createIdentify(int $rawId, PaymentQueryService $payments): View
    {
        $payment = $payments->find($rawId);

        abort_if($payment === null, 404);

        return view('payments.identify', ['payment' => $payment]);
    }

    public function identify(
        PaymentDocumentRequest $request,
        int $rawId,
        PaymentResolutionService $resolutions,
    ): RedirectResponse {
        $resolutions->identify(
            $rawId,
            $request->string('documento')->toString(),
            $request->string('motivo')->toString(),
            $request->user(),
        );

        return to_route('payments.show', $rawId)
            ->with('status', 'El pago fue identificado correctamente.');
    }

    public function edit(int $rawId, PaymentQueryService $payments): View
    {
        $payment = $payments->find($rawId);

        abort_if($payment === null, 404);

        return view('payments.edit-document', ['payment' => $payment]);
    }

    public function update(
        PaymentDocumentRequest $request,
        int $rawId,
        PaymentResolutionService $resolutions,
    ): RedirectResponse {
        $resolutions->correct(
            $rawId,
            $request->string('documento')->toString(),
            $request->string('motivo')->toString(),
            $request->user(),
        );

        return to_route('payments.show', $rawId)
            ->with('status', 'El documento del pago fue corregido correctamente.');
    }
}
