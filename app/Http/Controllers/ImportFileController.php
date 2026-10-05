<?php

namespace App\Http\Controllers;

use App\Services\Imports\ImportBatchQueryService;
use App\Services\Imports\ImportFileService;
use Symfony\Component\HttpFoundation\StreamedResponse;

class ImportFileController extends Controller
{
    public function __invoke(
        int $batchId,
        ImportBatchQueryService $batches,
        ImportFileService $files,
    ): StreamedResponse {
        $batch = $batches->find($batchId);

        abort_if($batch === null || ! $files->exists($batch->archivo_ruta), 404);

        return $files->disk()->download(
            $batch->archivo_ruta,
            $batch->archivo_original,
            [
                'Content-Type' => $batch->archivo_mime ?: 'application/octet-stream',
                'X-Content-Type-Options' => 'nosniff',
            ],
        );
    }
}
