<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\ImportOrigin;
use App\Models\User;
use App\RefreshMode;
use App\SearchSourceCode;
use Closure;
use Illuminate\Http\UploadedFile;
use Illuminate\Session\Store;
use Illuminate\Support\Str;

final class SearchImportPreviewService
{
    private const SESSION_PREFIX = 'search_import_preview.';

    public function __construct(
        private readonly ImportFileService $files,
        private readonly SearchSpreadsheetPreviewReader $reader,
        private readonly SearchPhonePreviewAnalyzer $phoneAnalyzer,
        private readonly SearchAssociatedPreviewAnalyzer $associatedAnalyzer,
        private readonly SearchImportDefinitionRegistry $definitions,
        private readonly SearchDatasetCatalogService $datasets,
        private readonly SearchSourceCatalogService $sources,
        private readonly Store $session,
    ) {}

    public function create(
        UploadedFile $file,
        DatasetCode $dataset,
        SearchSourceCode $source,
        RefreshMode $refreshMode,
        User $user,
    ): SearchImportPreview {
        $definition = $this->definitions->resolve($dataset);
        if (! in_array($refreshMode, $definition->refreshModes(), true)) {
            throw new InvalidImportFile('El modo de actualización no está habilitado para este dataset.');
        }
        $this->datasets->requireActive($dataset);
        $this->sources->requireAllowed($dataset, $source, $refreshMode);

        $sourcePath = $file->getRealPath();
        if ($sourcePath === false) {
            throw new InvalidImportFile('No se pudo acceder al archivo temporal de la carga.');
        }
        $maximumBytes = max(1, (int) config('imports.max_web_upload_mb')) * 1024 * 1024;
        $metadata = $this->files->inspect($sourcePath, $file->getClientOriginalName(), $maximumBytes);
        $token = Str::uuid()->toString();
        $storedPath = "search-previews/{$user->getAuthIdentifier()}/{$token}.{$metadata->extension}";
        $this->files->storeFromPath($sourcePath, $storedPath);

        try {
            $expectedMapping = $definition->suggest($definition->expectedHeaders());
            $path = $this->files->disk()->path($storedPath);
            $previewData = $definition->requiresFullPreviewAnalysis()
                ? $this->analyzeDataset(
                    $dataset,
                    $path,
                    $metadata->extension,
                    $expectedMapping,
                    (int) config('imports.search.preview_rows', 20),
                    (int) config('imports.search.preview_error_limit', 100),
                )
                : $this->reader->read(
                    $path,
                    $metadata->extension,
                    (int) config('imports.search.preview_rows', 20),
                );
            $preview = new SearchImportPreview(
                token: $token,
                userId: (int) $user->getAuthIdentifier(),
                datasetCode: $dataset->value,
                sourceCode: $source->value,
                refreshMode: $refreshMode->value,
                origin: ImportOrigin::Historical->value,
                storedPath: $storedPath,
                metadata: $metadata,
                headers: $previewData['headers'],
                rows: $previewData['rows'],
                suggestedMapping: $definition->suggest($previewData['headers']),
                expiresAt: now('UTC')->addMinutes((int) config('imports.search.preview_ttl_minutes', 30))->toIso8601String(),
                analysis: $previewData['analysis'] ?? null,
            );
            $this->session->put(self::SESSION_PREFIX.$token, $preview->toSession());

            return $preview;
        } catch (\Throwable $exception) {
            $this->files->delete($storedPath);
            throw $exception;
        }
    }

    public function get(string $token, User $user): SearchImportPreview
    {
        $values = $this->session->get(self::SESSION_PREFIX.$token);
        if (! is_array($values)) {
            throw new InvalidImportFile('El preview no existe o ya expiró.');
        }
        $preview = SearchImportPreview::fromSession($values);
        if ($preview->userId !== (int) $user->getAuthIdentifier() || now('UTC')->isAfter($preview->expiresAt)) {
            $this->forget($preview);
            throw new InvalidImportFile('El preview no existe o ya expiró.');
        }

        return $preview;
    }

    /** @param array<string, string> $mapping */
    public function analyze(SearchImportPreview $preview, array $mapping): ?SearchImportPreviewAnalysis
    {
        if ($preview->analysis !== null && $mapping === $preview->suggestedMapping) {
            return $preview->analysis;
        }

        return $this->readPreview($preview, $mapping)['analysis'] ?? null;
    }

    public function forget(SearchImportPreview $preview, bool $deleteFile = true): void
    {
        $this->session->forget(self::SESSION_PREFIX.$preview->token);
        if ($deleteFile) {
            $this->files->delete($preview->storedPath);
        }
    }

    /**
     * @param  Closure(array{row: int, document: string|null, phone: string|null, field: string, error: string, message: string, value: string}): void  $writeError
     */
    public function writeErrors(SearchImportPreview $preview, Closure $writeError): SearchImportPreviewAnalysis
    {
        $definition = $this->definitions->resolve(DatasetCode::from($preview->datasetCode));
        if (! $definition->requiresFullPreviewAnalysis()) {
            throw new InvalidImportFile('El dataset no admite un reporte de errores detallado.');
        }

        $dataset = DatasetCode::from($preview->datasetCode);
        if ($dataset === DatasetCode::Telefonos) {
            return $this->phoneAnalyzer->writeErrors(
                $this->files->disk()->path($preview->storedPath),
                $preview->metadata->extension,
                $preview->suggestedMapping,
                $writeError,
            );
        }

        return $this->associatedAnalyzer->writeErrors(
            $dataset,
            $this->files->disk()->path($preview->storedPath),
            $preview->metadata->extension,
            $preview->suggestedMapping,
            static function (array $event) use ($writeError): void {
                if (! $event['warning']) {
                    $writeError($event);
                }
            },
        );
    }

    /**
     * @param  array<string, string>  $mapping
     * @return array{headers: list<string>, rows: list<list<string|null>>, analysis?: SearchImportPreviewAnalysis}
     */
    private function readPreview(SearchImportPreview $preview, array $mapping): array
    {
        $path = $this->files->disk()->path($preview->storedPath);
        $limit = (int) config('imports.search.preview_rows', 20);
        $definition = $this->definitions->resolve(DatasetCode::from($preview->datasetCode));
        if ($definition->requiresFullPreviewAnalysis()) {
            return $this->analyzeDataset(
                DatasetCode::from($preview->datasetCode),
                $path,
                $preview->metadata->extension,
                $mapping,
                $limit,
                (int) config('imports.search.preview_error_limit', 100),
            );
        }

        return $this->reader->read($path, $preview->metadata->extension, $limit);
    }

    /** @param array<string, string> $mapping */
    private function analyzeDataset(
        DatasetCode $dataset,
        string $path,
        string $extension,
        array $mapping,
        int $previewLimit,
        int $errorLimit,
    ): array {
        if ($dataset === DatasetCode::Telefonos) {
            return $this->phoneAnalyzer->analyze($path, $extension, $mapping, $previewLimit, $errorLimit);
        }

        return $this->associatedAnalyzer->analyze($dataset, $path, $extension, $mapping, $previewLimit, $errorLimit);
    }
}
