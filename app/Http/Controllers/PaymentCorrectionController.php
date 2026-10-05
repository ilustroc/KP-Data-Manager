<?php

namespace App\Http\Controllers;

use App\Http\Requests\Payments\CorrectionIndexRequest;
use App\Services\Payments\PaymentQueryService;
use Illuminate\View\View;

class PaymentCorrectionController extends Controller
{
    /**
     * Handle the incoming request.
     */
    public function __invoke(CorrectionIndexRequest $request, PaymentQueryService $payments): View
    {
        $filters = $request->validated();

        return view('payments.corrections', [
            'corrections' => $payments->paginateCorrections($filters)->withQueryString(),
            'filters' => $filters,
        ]);
    }
}
