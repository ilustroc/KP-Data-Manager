<?php

namespace App\Services\Imports;

use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use App\Models\User;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use Throwable;

class ImportUploadService
{
    public function __construct(private readonly ImportFileService $files) {}

    public function registerWeb(
        UploadedFile $file,
        ImportType $type,
        ImportOrigin $origin,
        User $user,
    ): int {
        $sourcePath = $file->getRealPath();

        if ($sourcePath === false) {
            throw new InvalidImportFile('No se pudo acceder al archivo temporal de la carga.');
        }

        $maximumBytes = max(1, (int) config('imports.max_web_upload_mb')) * 1024 * 1024;
        $metadata = $this->files->inspect($sourcePath, $file->getClientOriginalName(), $maximumBytes);

        return $this->register(
            sourcePath: $sourcePath,
            metadata: $metadata,
            type: $type,
            origin: $origin,
            auditor: 'user:'.$user->getAuthIdentifier(),
            removeSourceAfterRegistration: false,
        );
    }

    public function registerInbox(
        string $sourcePath,
        string $originalName,
        ImportType $type,
        ImportOrigin $origin,
        string $auditor,
    ): int {
        $metadata = $this->files->inspect($sourcePath, $originalName);

        return $this->register(
            sourcePath: $sourcePath,
            metadata: $metadata,
            type: $type,
            origin: $origin,
            auditor: $auditor,
            removeSourceAfterRegistration: true,
        );
    }

    private function register(
        string $sourcePath,
        ImportFileMetadata $metadata,
        ImportType $type,
        ImportOrigin $origin,
        string $auditor,
        bool $removeSourceAfterRegistration,
    ): int {
        $connection = $this->connection();
        $lockName = 'kpdm:import-sha:'.substr($metadata->sha256, 0, 40);
        $hasLock = $this->acquireHashLock($connection, $lockName);

        if (! $hasLock) {
            throw new ImportRegistrationFailed('Otra solicitud está registrando este mismo archivo. Intenta nuevamente.');
        }

        try {
            $duplicateBatchId = $connection
                ->table(config('imports.table'))
                ->where('archivo_sha256', $metadata->sha256)
                ->value('batch_id');

            if ($duplicateBatchId !== null) {
                throw new DuplicateImportFile((int) $duplicateBatchId);
            }

            return $this->persistFileAndBatch(
                connection: $connection,
                sourcePath: $sourcePath,
                metadata: $metadata,
                type: $type,
                origin: $origin,
                auditor: $auditor,
                removeSourceAfterRegistration: $removeSourceAfterRegistration,
            );
        } finally {
            $this->releaseHashLock($connection, $lockName);
        }
    }

    private function persistFileAndBatch(
        ConnectionInterface $connection,
        string $sourcePath,
        ImportFileMetadata $metadata,
        ImportType $type,
        ImportOrigin $origin,
        string $auditor,
        bool $removeSourceAfterRegistration,
    ): int {
        $batchId = null;
        $temporaryPath = '';
        $finalPath = '';

        try {
            $internalName = Str::uuid()->toString().'.'.$metadata->extension;
            $batchId = (int) $connection->table(config('imports.table'))->insertGetId([
                'tipo' => $type->value,
                'origen' => $origin->value,
                'archivo' => $metadata->originalName,
                'archivo_original' => $metadata->originalName,
                'archivo_interno' => $internalName,
                'archivo_ruta' => null,
                'archivo_extension' => $metadata->extension,
                'archivo_mime' => $metadata->mimeType,
                'archivo_tamano' => $metadata->size,
                'archivo_sha256' => $metadata->sha256,
                'fecha_inicio' => now('UTC')->format('Y-m-d H:i:s'),
                'fecha_fin' => null,
                'estado' => ImportStatus::Received->value,
                'filas_archivo' => 0,
                'filas_insertadas' => 0,
                'filas_duplicadas' => 0,
                'filas_error' => 0,
                'usuario' => $auditor,
                'mensaje_error' => null,
            ], 'batch_id');

            $directory = now('UTC')->format('Y/m').'/'.$batchId;
            $finalPath = $directory.'/'.$internalName;
            $temporaryPath = $finalPath.'.part';

            $this->files->storeFromPath($sourcePath, $temporaryPath);
            $this->files->move($temporaryPath, $finalPath);

            $updated = $this->transitionBatch(
                connection: $connection,
                batchId: $batchId,
                from: ImportStatus::Received,
                to: ImportStatus::Pending,
                values: ['archivo_ruta' => $finalPath],
            );

            if ($updated !== 1) {
                throw new ImportRegistrationFailed('No se pudo finalizar el registro de la carga.');
            }

            if ($removeSourceAfterRegistration && ! unlink($sourcePath)) {
                throw new ImportRegistrationFailed('No se pudo retirar el archivo del inbox después de registrarlo.');
            }

            Log::info('Archivo de importación registrado.', [
                'batch_id' => $batchId,
                'archivo' => $metadata->originalName,
                'tipo' => $type->value,
                'origen' => $origin->value,
                'estado' => ImportStatus::Pending->value,
                'tamano_bytes' => $metadata->size,
                'sha256' => $metadata->sha256,
                'usuario' => $auditor,
            ]);

            return $batchId;
        } catch (DuplicateImportFile|InvalidImportFile $exception) {
            throw $exception;
        } catch (Throwable $exception) {
            $this->removeStoredFileSafely($temporaryPath, $batchId);
            $this->removeStoredFileSafely($finalPath, $batchId);

            if ($batchId !== null) {
                $this->markBatchAsFailed($connection, $batchId);
            }

            Log::error('No se pudo registrar el archivo de importación.', [
                'batch_id' => $batchId,
                'archivo' => $metadata->originalName,
                'sha256' => $metadata->sha256,
                'exception' => $exception,
            ]);

            throw new ImportRegistrationFailed(
                'No se pudo almacenar y registrar el archivo. La carga quedó marcada con error.',
                previous: $exception,
            );
        }
    }

    private function markBatchAsFailed(ConnectionInterface $connection, int $batchId): void
    {
        try {
            $currentValue = $connection
                ->table(config('imports.table'))
                ->where('batch_id', $batchId)
                ->value('estado');
            $current = is_string($currentValue) ? ImportStatus::tryFrom($currentValue) : null;

            if ($current !== null && $current->canTransitionTo(ImportStatus::Error)) {
                $this->transitionBatch(
                    connection: $connection,
                    batchId: $batchId,
                    from: $current,
                    to: ImportStatus::Error,
                    values: ['mensaje_error' => 'Fallo al almacenar o finalizar el registro del archivo.'],
                );
            }
        } catch (Throwable $exception) {
            Log::critical('No se pudo marcar como ERROR un batch de importación inconsistente.', [
                'batch_id' => $batchId,
                'exception' => $exception,
            ]);
        }
    }

    private function acquireHashLock(ConnectionInterface $connection, string $lockName): bool
    {
        if ($connection->getDriverName() !== 'mysql') {
            return true;
        }

        $result = $connection->selectOne('SELECT GET_LOCK(?, 10) AS acquired', [$lockName]);

        return (int) ($result->acquired ?? 0) === 1;
    }

    private function releaseHashLock(ConnectionInterface $connection, string $lockName): void
    {
        if ($connection->getDriverName() !== 'mysql') {
            return;
        }

        try {
            $connection->selectOne('SELECT RELEASE_LOCK(?) AS released', [$lockName]);
        } catch (Throwable $exception) {
            Log::warning('No se pudo liberar inmediatamente el bloqueo de hash de importación.', [
                'lock' => $lockName,
                'exception' => $exception,
            ]);
        }
    }

    /**
     * @param  array<string, mixed>  $values
     */
    private function transitionBatch(
        ConnectionInterface $connection,
        int $batchId,
        ImportStatus $from,
        ImportStatus $to,
        array $values = [],
    ): int {
        if (! $from->canTransitionTo($to)) {
            throw new ImportRegistrationFailed("La transición {$from->value} → {$to->value} no está permitida.");
        }

        return $connection
            ->table(config('imports.table'))
            ->where('batch_id', $batchId)
            ->where('estado', $from->value)
            ->update(array_merge($values, ['estado' => $to->value]));
    }

    private function removeStoredFileSafely(string $path, ?int $batchId): void
    {
        try {
            $this->files->delete($path);
        } catch (Throwable $exception) {
            Log::critical('No se pudo limpiar un archivo de importación después de un fallo.', [
                'batch_id' => $batchId,
                'path' => $path,
                'exception' => $exception,
            ]);
        }
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.connection'));
    }
}
