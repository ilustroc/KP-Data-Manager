<?php

namespace App\Http\Controllers;

use App\Http\Requests\Imports\DeleteHistoricalPortfolioImportRequest;
use App\Services\Imports\HistoricalPortfolioImportDeletionService;
use App\Services\Imports\ImportDeletionFailed;
use App\Services\Imports\ImportDeletionNotAllowed;
use Illuminate\Http\RedirectResponse;

class ImportDeletionController extends Controller
{
    public function __invoke(
        DeleteHistoricalPortfolioImportRequest $request,
        int $batchId,
        HistoricalPortfolioImportDeletionService $deletion,
    ): RedirectResponse {
        try {
            $result = $deletion->delete($batchId, $request->user());
        } catch (ImportDeletionNotAllowed|ImportDeletionFailed $exception) {
            return back()->with('warning', $exception->getMessage());
        }

        $message = $result->warning === null
            ? "Carga #{$batchId} eliminada correctamente."
            : "Carga #{$batchId} eliminada. {$result->warning}";

        return redirect()->route('imports.index')->with(
            $result->warning === null ? 'status' : 'warning',
            $message,
        );
    }
}
