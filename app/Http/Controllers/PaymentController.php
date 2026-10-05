<?php

namespace App\Http\Controllers;

use App\Http\Requests\Payments\PaymentIndexRequest;
use App\Services\Payments\PaymentQueryService;
use Illuminate\View\View;

class PaymentController extends Controller
{
    public function index(PaymentIndexRequest $request, PaymentQueryService $payments): View
    {
        $filters = $request->validated();

        return view('payments.index', [
            'filters' => $filters,
            'payments' => $payments->paginateCurrent($filters)->withQueryString(),
        ]);
    }

    public function unidentified(PaymentIndexRequest $request, PaymentQueryService $payments): View
    {
        $filters = $request->safe()->except(['documento', 'estado']);

        return view('payments.unidentified', [
            'filters' => $filters,
            'payments' => $payments->paginateUnidentified($filters)->withQueryString(),
        ]);
    }

    public function show(int $rawId, PaymentQueryService $payments): View
    {
        $payment = $payments->find($rawId);

        abort_if($payment === null, 404);

        return view('payments.show', ['payment' => $payment]);
    }
}
