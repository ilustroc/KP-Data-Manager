<?php

namespace App\Http\Controllers;

use App\DatasetCode;
use App\Http\Requests\Imports\ConfirmSearchImportRequest;
use App\Http\Requests\Imports\PreviewSearchImportRequest;
use App\RefreshMode;
use App\SearchSourceCode;
use App\Services\Imports\DuplicateImportFile;
use App\Services\Imports\ImportBatchDispatcher;
use App\Services\Imports\ImportDispatchFailed;
use App\Services\Imports\ImportRegistrationFailed;
use App\Services\Imports\InvalidImportFile;
use App\Services\Imports\SearchImportConfigurationException;
use App\Services\Imports\SearchImportDefinitionRegistry;
use App\Services\Imports\SearchImportPreviewService;
use App\Services\Imports\SearchImportRegistrationService;
use Illuminate\Http\RedirectResponse;
use Illuminate\View\View;
use Symfony\Component\HttpFoundation\StreamedResponse;

final class SearchImportController extends Controller
{
    public function preview(
        PreviewSearchImportRequest $request,
        SearchImportPreviewService $previews,
    ): RedirectResponse {
        $validated = $request->validated();
        try {
            $preview = $previews->create(
                $request->file('archivo'),
                DatasetCode::from($validated['dataset_code']),
                SearchSourceCode::from($validated['source_code']),
                RefreshMode::from($validated['refresh_mode']),
                $request->user(),
            );
        } catch (InvalidImportFile|SearchImportConfigurationException $exception) {
            return back()->withInput($request->except('archivo'))->withErrors(['archivo' => $exception->getMessage()]);
        }

        return redirect()->route('imports.search.preview.show', $preview->token);
    }

    public function show(
        string $token,
        SearchImportPreviewService $previews,
        SearchImportDefinitionRegistry $definitions,
    ): View|RedirectResponse {
        try {
            $preview = $previews->get($token, request()->user());
        } catch (InvalidImportFile $exception) {
            return redirect()->route('imports.create')->withErrors(['archivo' => $exception->getMessage()]);
        }

        $definition = $definitions->resolve(DatasetCode::from($preview->datasetCode));

        return view('imports.search-preview', [
            'preview' => $preview,
            'fields' => $definition->fields(),
        ]);
    }

    public function confirm(
        ConfirmSearchImportRequest $request,
        SearchImportPreviewService $previews,
        SearchImportRegistrationService $registration,
        ImportBatchDispatcher $dispatcher,
        SearchImportDefinitionRegistry $definitions,
    ): RedirectResponse {
        $validated = $request->validated();
        try {
            $preview = $previews->get($validated['token'], $request->user());
            $mapping = $validated['mapping'];
            $definition = $definitions->resolve(DatasetCode::from($preview->datasetCode));
            $this->assertValidMapping($mapping, $preview->headers, $definition->requiredFields());
            $analysis = $previews->analyze($preview, $mapping);
            if ($analysis !== null && ! $analysis->isReady()) {
                throw new InvalidImportFile('El archivo no es apto para procesar. Corrige los errores del preview.');
            }
            $batchId = $registration->register($preview, $mapping, $request->user());
            $previews->forget($preview, deleteFile: false);
            $dispatcher->dispatch($batchId);
        } catch (DuplicateImportFile $exception) {
            $previews->forget($preview);

            return redirect()->route('imports.show', $exception->batchId)->with('warning', $exception->getMessage());
        } catch (InvalidImportFile|ImportRegistrationFailed|SearchImportConfigurationException $exception) {
            return back()->withInput()->withErrors(['mapping' => $exception->getMessage()]);
        } catch (ImportDispatchFailed) {
            return redirect()->route('imports.show', $batchId)
                ->with('warning', "La carga #{$batchId} fue registrada, pero no fue posible enviarla a procesamiento.");
        }

        return redirect()->route('imports.show', $batchId)
            ->with('status', "La carga SEARCH #{$batchId} fue confirmada y enviada a procesamiento.");
    }

    public function downloadErrors(
        string $token,
        SearchImportPreviewService $previews,
    ): StreamedResponse|RedirectResponse {
        try {
            $preview = $previews->get($token, request()->user());
        } catch (InvalidImportFile $exception) {
            return redirect()->route('imports.create')->withErrors(['archivo' => $exception->getMessage()]);
        }

        if ($preview->analysis === null || $preview->analysis->totalErrors === 0) {
            return redirect()
                ->route('imports.search.preview.show', $preview->token)
                ->with('warning', 'El preview no contiene errores para descargar.');
        }

        $filename = 'errores_'.$preview->datasetCode.'_'.now('America/Lima')->format('Ymd_His').'.csv';

        return response()->streamDownload(
            function () use ($previews, $preview): void {
                $stream = fopen('php://output', 'wb');
                if ($stream === false) {
                    return;
                }

                try {
                    fwrite($stream, "\xEF\xBB\xBF");
                    fputcsv($stream, ['FILA', 'DOCUMENTO', 'TELEFONO', 'CAMPO', 'CODIGO_ERROR', 'DESCRIPCION', 'VALOR_ORIGINAL']);
                    $previews->writeErrors($preview, function (array $error) use ($stream): void {
                        fputcsv($stream, [
                            $error['row'],
                            $error['document'],
                            $error['phone'],
                            $error['field'],
                            $error['error'],
                            $error['message'],
                            $error['value'],
                        ]);
                    });
                } finally {
                    fclose($stream);
                }
            },
            $filename,
            [
                'Content-Type' => 'text/csv; charset=UTF-8',
                'X-Content-Type-Options' => 'nosniff',
            ],
        );
    }

    /**
     * @param  array<string, string>  $mapping
     * @param  list<string>  $headers
     * @param  list<string>  $targets
     */
    private function assertValidMapping(array $mapping, array $headers, array $targets): void
    {
        if (count($mapping) !== count($targets)
            || array_diff($targets, array_keys($mapping)) !== []
            || count(array_unique($mapping)) !== count($mapping)) {
            throw new InvalidImportFile('El mapping debe asignar una columna distinta a cada campo canónico.');
        }
        foreach ($mapping as $sourceHeader) {
            if (! in_array($sourceHeader, $headers, true)) {
                throw new InvalidImportFile('El mapping contiene una columna que no pertenece al archivo previsualizado.');
            }
        }
    }
}
