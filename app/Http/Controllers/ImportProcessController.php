<?php

namespace App\Http\Controllers;

use App\ImportStatus;
use App\Services\Imports\ImportBatchDispatcher;
use App\Services\Imports\ImportBatchQueryService;
use App\Services\Imports\ImportDispatchFailed;
use Illuminate\Http\RedirectResponse;
use Symfony\Component\HttpFoundation\Response;

class ImportProcessController extends Controller
{
    public function __invoke(
        int $batchId,
        ImportBatchQueryService $batches,
        ImportBatchDispatcher $dispatcher,
    ): RedirectResponse {
        $batch = $batches->find($batchId);

        abort_if($batch === null, Response::HTTP_NOT_FOUND);
        abort_unless(
            $batch->estado === ImportStatus::Pending->value,
            Response::HTTP_UNPROCESSABLE_ENTITY,
            'Solo las cargas pendientes pueden enviarse a procesamiento.',
        );

        try {
            $dispatcher->dispatch($batchId);
        } catch (ImportDispatchFailed) {
            return redirect()
                ->route('imports.show', $batchId)
                ->with('warning', 'No fue posible enviar la carga a procesamiento.');
        }

        return redirect()
            ->route('imports.show', $batchId)
            ->with('status', 'El procesamiento fue enviado a la cola.');
    }
}
