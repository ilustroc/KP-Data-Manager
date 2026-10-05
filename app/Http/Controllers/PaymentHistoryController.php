<?php

namespace App\Http\Controllers;

use App\Services\Payments\PaymentQueryService;
use Illuminate\View\View;

class PaymentHistoryController extends Controller
{
    /**
     * Handle the incoming request.
     */
    public function __invoke(int $rawId, PaymentQueryService $payments): View
    {
        $payment = $payments->find($rawId);

        abort_if($payment === null, 404);

        return view('payments.history', [
            'history' => $payments->history($rawId),
            'payment' => $payment,
        ]);
    }
}
