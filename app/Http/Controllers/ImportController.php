<?php

namespace App\Http\Controllers;

use App\DatasetCode;
use App\FinancialEntity;
use App\Http\Requests\Imports\ImportIndexRequest;
use App\Http\Requests\Imports\StoreImportRequest;
use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use App\Services\Imports\DuplicateImportFile;
use App\Services\Imports\HistoricalPortfolioImportDeletionService;
use App\Services\Imports\ImportBatchDispatcher;
use App\Services\Imports\ImportBatchProcessingService;
use App\Services\Imports\ImportBatchQueryService;
use App\Services\Imports\ImportDispatchFailed;
use App\Services\Imports\ImportFileService;
use App\Services\Imports\ImportRegistrationFailed;
use App\Services\Imports\ImportUploadService;
use App\Services\Imports\InvalidImportFile;
use App\Services\Imports\SearchSourceCatalogService;
use Illuminate\Http\RedirectResponse;
use Illuminate\View\View;

class ImportController extends Controller
{
    public function index(ImportIndexRequest $request, ImportBatchQueryService $batches): View
    {
        $filters = $request->validated();

        return view('imports.index', [
            'batches' => $batches->paginate($filters),
            'filters' => $filters,
            'types' => ImportType::cases(),
            'entities' => FinancialEntity::cases(),
            'origins' => ImportOrigin::cases(),
            'statuses' => ImportStatus::cases(),
        ]);
    }

    public function create(SearchSourceCatalogService $sources): View
    {
        $registrationTypes = config('imports.registration_types', []);
        $searchSources = [];
        if ((bool) config('imports.search.registration_enabled')) {
            foreach (config('imports.search.available_datasets', []) as $datasetCode) {
                $dataset = DatasetCode::tryFrom($datasetCode);
                if ($dataset !== null) {
                    $searchSources[$dataset->value] = $sources->activeForDataset($dataset);
                }
            }
        }

        return view('imports.create', [
            'types' => array_values(array_filter(
                ImportType::cases(),
                static fn (ImportType $type): bool => $type !== ImportType::Search
                    && in_array($type->value, $registrationTypes, true),
            )),
            'entities' => FinancialEntity::cases(),
            'origins' => ImportOrigin::cases(),
            'maximumUploadMegabytes' => (int) config('imports.max_web_upload_mb'),
            'searchEnabled' => (bool) config('imports.search.registration_enabled'),
            'searchDatasets' => DatasetCode::cases(),
            'searchSources' => $searchSources,
        ]);
    }

    public function store(
        StoreImportRequest $request,
        ImportUploadService $uploads,
        ImportBatchProcessingService $processing,
        ImportBatchDispatcher $dispatcher,
    ): RedirectResponse {
        $validated = $request->validated();
        $entity = isset($validated['entidad'])
            ? FinancialEntity::from($validated['entidad'])
            : null;

        try {
            $batchId = $uploads->registerWeb(
                file: $request->file('archivo'),
                type: ImportType::from($validated['tipo']),
                origin: ImportOrigin::from($validated['origen']),
                entity: $entity,
                user: $request->user(),
            );
        } catch (DuplicateImportFile|InvalidImportFile|ImportRegistrationFailed $exception) {
            return back()->withInput($request->except('archivo'))->withErrors([
                'archivo' => $exception->getMessage(),
            ]);
        }

        if ($processing->status($batchId) !== ImportStatus::Pending) {
            return redirect()
                ->route('imports.show', $batchId)
                ->with('warning', "La carga #{$batchId} fue registrada, pero no pudo enviarse a procesamiento.");
        }

        try {
            $dispatcher->dispatch($batchId);
        } catch (ImportDispatchFailed) {
            return redirect()
                ->route('imports.show', $batchId)
                ->with('warning', "La carga #{$batchId} fue registrada, pero no fue posible enviarla a procesamiento.");
        }

        return redirect()
            ->route('imports.show', $batchId)
            ->with('status', "La carga #{$batchId} fue registrada y enviada a procesamiento.");
    }

    public function show(
        int $batchId,
        ImportBatchQueryService $batches,
        ImportFileService $files,
        HistoricalPortfolioImportDeletionService $deletion,
    ): View {
        $batch = $batches->find($batchId);

        abort_if($batch === null, 404);

        return view('imports.show', [
            'batch' => $batch,
            'importErrors' => $batches->paginateErrors($batchId),
            'fileIsStored' => $files->exists($batch->archivo_ruta),
            'deletionAllowed' => $deletion->isEligible($batch),
        ]);
    }
}
