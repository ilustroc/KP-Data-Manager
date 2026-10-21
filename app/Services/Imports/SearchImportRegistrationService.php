<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\ImportStatus;
use App\ImportType;
use App\Models\User;
use App\RefreshMode;
use App\SearchSourceCode;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Throwable;

final class SearchImportRegistrationService
{
    public function __construct(
        private readonly ImportFileService $files,
        private readonly ImportFileAccessService $fileAccess,
        private readonly ImportColumnMappingService $mappings,
        private readonly SearchImportIdempotencyKey $idempotency,
        private readonly SearchImportDefinitionRegistry $definitions,
        private readonly SearchDatasetCatalogService $datasets,
        private readonly SearchSourceCatalogService $sources,
    ) {}

    /** @param array<string, string> $mapping */
    public function register(SearchImportPreview $preview, array $mapping, User $user): int
    {
        $dataset = DatasetCode::from($preview->datasetCode);
        $source = SearchSourceCode::from($preview->sourceCode);
        $refreshMode = RefreshMode::from($preview->refreshMode);
        $definition = $this->definitions->resolve($dataset);
        if (! in_array($refreshMode, $definition->refreshModes(), true)) {
            throw new SearchImportConfigurationException('El modo de actualización no está habilitado para este dataset.');
        }
        $this->datasets->requireActive($dataset);
        $this->sources->requireAllowed($dataset, $source, $refreshMode);

        $mappingVersion = $this->mappings->createOrReuse(
            $dataset,
            $source,
            $preview->headers,
            $mapping,
            $dataset->value.'_V'.$definition->profileVersion(),
        );
        $key = $this->idempotency->make(
            $dataset,
            $source,
            $refreshMode,
            $definition->profileVersion(),
            $mappingVersion,
            $preview->metadata->sha256,
        );
        $connection = $this->connection();
        $duplicate = $connection->table(config('imports.table'))->where('idempotency_key', $key)->value('batch_id');
        if ($duplicate !== null) {
            throw new DuplicateImportFile((int) $duplicate);
        }

        $batchId = null;
        $destination = '';
        try {
            $registeredAt = now('UTC');
            $internalName = Str::uuid()->toString().'.'.$preview->metadata->extension;
            $batchId = (int) $connection->table(config('imports.table'))->insertGetId([
                'tipo' => ImportType::Search->value,
                'entidad' => null,
                'perfil_version' => $definition->profileVersion(),
                'dataset_code' => $dataset->value,
                'source_code' => $source->value,
                'refresh_mode' => $refreshMode->value,
                'origen' => $preview->origin,
                'archivo' => $preview->metadata->originalName,
                'archivo_original' => $preview->metadata->originalName,
                'archivo_interno' => $internalName,
                'archivo_ruta' => null,
                'archivo_extension' => $preview->metadata->extension,
                'archivo_mime' => $preview->metadata->mimeType,
                'archivo_tamano' => $preview->metadata->size,
                'archivo_sha256' => $preview->metadata->sha256,
                'fecha_inicio' => $registeredAt->format('Y-m-d H:i:s'),
                'fecha_fin' => null,
                'estado' => ImportStatus::Received->value,
                'filas_archivo' => 0,
                'filas_insertadas' => 0,
                'filas_duplicadas' => 0,
                'filas_error' => 0,
                'rows_valid' => 0,
                'rows_invalid' => 0,
                'rows_published' => 0,
                'scope_count' => 0,
                'received_at' => $registeredAt->format('Y-m-d H:i:s'),
                'validated_at' => null,
                'published_at' => null,
                'uploaded_by_user_id' => $user->getAuthIdentifier(),
                'mapping_version' => $mappingVersion,
                'idempotency_key' => $key,
                'usuario' => 'user:'.$user->getAuthIdentifier(),
                'mensaje_error' => null,
            ], 'batch_id');
            $destination = $this->files->pathForBatch($batchId, $internalName, $registeredAt);
            $this->files->move($preview->storedPath, $destination);
            $this->fileAccess->prepare($destination);
            $updated = $connection->table(config('imports.table'))
                ->where('batch_id', $batchId)
                ->where('estado', ImportStatus::Received->value)
                ->update(['archivo_ruta' => $destination, 'estado' => ImportStatus::Pending->value]);
            if ($updated !== 1) {
                throw new ImportRegistrationFailed('No se pudo finalizar el registro SEARCH.');
            }

            return $batchId;
        } catch (DuplicateImportFile $exception) {
            throw $exception;
        } catch (Throwable $exception) {
            if ($destination !== '') {
                $this->files->delete($destination);
            }
            if ($batchId !== null) {
                $connection->table(config('imports.table'))->where('batch_id', $batchId)->update([
                    'estado' => ImportStatus::Error->value,
                    'fecha_fin' => now('UTC')->format('Y-m-d H:i:s'),
                    'mensaje_error' => 'No se pudo finalizar el registro SEARCH.',
                ]);
            }
            throw new ImportRegistrationFailed('No se pudo almacenar y registrar la carga SEARCH.', previous: $exception);
        }
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.search.control_connection'));
    }
}
