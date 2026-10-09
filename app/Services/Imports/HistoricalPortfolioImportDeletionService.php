<?php

namespace App\Services\Imports;

use App\ImportOrigin;
use App\ImportStatus;
use App\ImportType;
use App\Models\User;
use App\UserRole;
use Carbon\CarbonImmutable;
use Illuminate\Auth\Access\AuthorizationException;
use Illuminate\Database\ConnectionInterface;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use RuntimeException;
use Throwable;

final class HistoricalPortfolioImportDeletionService
{
    private const array TERMINAL_STATUSES = [
        ImportStatus::Completed,
        ImportStatus::CompletedWithErrors,
        ImportStatus::Error,
    ];

    public function __construct(private readonly ImportFileService $files) {}

    public function isEligible(object $batch): bool
    {
        $status = ImportStatus::tryFrom((string) ($batch->estado ?? ''));

        return ($batch->tipo ?? null) === ImportType::Portfolio->value
            && ($batch->origen ?? null) === ImportOrigin::Historical->value
            && is_string($batch->entidad ?? null)
            && array_key_exists($batch->entidad, $this->entityTables())
            && $status !== null
            && in_array($status, self::TERMINAL_STATUSES, true);
    }

    /**
     * @throws AuthorizationException
     * @throws ImportDeletionFailed
     * @throws ImportDeletionNotAllowed
     * @throws ModelNotFoundException
     */
    public function delete(int $batchId, User $user): ImportDeletionResult
    {
        if (! $user->is_active || ! $user->hasRole(UserRole::Admin)) {
            throw new AuthorizationException;
        }

        $connection = $this->connection();
        $snapshot = $this->findBatch($connection, $batchId);
        $this->assertEligible($snapshot);

        try {
            /** @var array{audit_id: int, stored_path: string|null} $transactionResult */
            $transactionResult = $connection->transaction(function () use ($connection, $batchId, $user): array {
                $batch = $connection
                    ->table(config('imports.table'))
                    ->where('batch_id', $batchId)
                    ->lockForUpdate()
                    ->first();

                if ($batch === null) {
                    throw (new ModelNotFoundException)->setModel('import_batch', [$batchId]);
                }

                $this->assertEligible($batch);
                $storedPath = $this->resolveStoredPath($batch);
                $auditId = (int) $connection
                    ->table(config('imports.deletion.audit_table'))
                    ->insertGetId($this->auditValues($batch, $user));

                foreach ($this->tablesFor((string) $batch->entidad) as $table) {
                    $connection->table($table)->where('batch_id', $batchId)->delete();
                }

                $connection
                    ->table(config('imports.error_table'))
                    ->where('batch_id', $batchId)
                    ->delete();

                $deleted = $connection
                    ->table(config('imports.table'))
                    ->where('batch_id', $batchId)
                    ->delete();

                if ($deleted !== 1) {
                    throw new ImportDeletionFailed('No fue posible eliminar el registro de la carga.');
                }

                return [
                    'audit_id' => $auditId,
                    'stored_path' => $storedPath,
                ];
            }, 1);
        } catch (AuthorizationException|ImportDeletionNotAllowed|ModelNotFoundException $exception) {
            throw $exception;
        } catch (Throwable $exception) {
            Log::error('Falló la eliminación transaccional de una carga histórica.', [
                'batch_id' => $batchId,
                'exception' => $exception,
            ]);

            throw new ImportDeletionFailed(
                'No fue posible eliminar la carga. No se realizó ningún cambio.',
                previous: $exception,
            );
        }

        [$fileDeleted, $warning] = $this->deletePhysicalFile($transactionResult['stored_path'], $batchId);
        $this->updateFileAudit($connection, $transactionResult['audit_id'], $fileDeleted, $warning, $batchId);

        return new ImportDeletionResult($batchId, $fileDeleted, $warning);
    }

    private function resolveStoredPath(object $batch): ?string
    {
        if (is_string($batch->archivo_ruta ?? null) && trim($batch->archivo_ruta) !== '') {
            return $this->safeStoredPath($batch->archivo_ruta);
        }

        if (! is_string($batch->archivo_interno ?? null) || trim($batch->archivo_interno) === '') {
            return null;
        }

        if (! is_string($batch->fecha_inicio ?? null) || trim($batch->fecha_inicio) === '') {
            throw new ImportDeletionNotAllowed('Los metadatos privados registrados para el archivo no son válidos.');
        }

        try {
            $registeredAt = CarbonImmutable::parse($batch->fecha_inicio, 'UTC');
            $reconstructedPath = $this->files->pathForBatch(
                (int) ($batch->batch_id ?? 0),
                $batch->archivo_interno,
                $registeredAt,
            );
        } catch (Throwable) {
            throw new ImportDeletionNotAllowed('Los metadatos privados registrados para el archivo no son válidos.');
        }

        return $this->safeStoredPath($reconstructedPath);
    }

    private function findBatch(ConnectionInterface $connection, int $batchId): object
    {
        $batch = $connection
            ->table(config('imports.table'))
            ->where('batch_id', $batchId)
            ->first();

        if ($batch === null) {
            throw (new ModelNotFoundException)->setModel('import_batch', [$batchId]);
        }

        return $batch;
    }

    private function assertEligible(object $batch): void
    {
        if (($batch->tipo ?? null) !== ImportType::Portfolio->value) {
            throw new ImportDeletionNotAllowed('Solo se pueden eliminar cargas históricas de cartera.');
        }

        if (($batch->origen ?? null) !== ImportOrigin::Historical->value) {
            throw new ImportDeletionNotAllowed('La carga no corresponde a un origen histórico.');
        }

        $status = ImportStatus::tryFrom((string) ($batch->estado ?? ''));
        if ($status === null || ! in_array($status, self::TERMINAL_STATUSES, true)) {
            throw new ImportDeletionNotAllowed('La carga debe estar en un estado terminal para poder eliminarse.');
        }

        if (! is_string($batch->entidad ?? null) || ! array_key_exists($batch->entidad, $this->entityTables())) {
            throw new ImportDeletionNotAllowed('La entidad de la carga no admite eliminación controlada.');
        }
    }

    private function safeStoredPath(mixed $storedPath): ?string
    {
        if (! is_string($storedPath) || trim($storedPath) === '') {
            return null;
        }

        $path = str_replace('\\', '/', trim($storedPath));
        $segments = explode('/', $path);
        $isAbsolute = str_starts_with($path, '/')
            || preg_match('/^[A-Za-z]:\//', $path) === 1;
        $hasUnsafeSegment = in_array('..', $segments, true)
            || in_array('.', $segments, true)
            || in_array('', $segments, true);

        if ($isAbsolute || $hasUnsafeSegment || str_contains($path, "\0")) {
            throw new ImportDeletionNotAllowed('La ubicación privada registrada para el archivo no es válida.');
        }

        return $path;
    }

    /**
     * @return array{bool, string|null}
     */
    private function deletePhysicalFile(?string $storedPath, int $batchId): array
    {
        if ($storedPath === null || ! $this->files->exists($storedPath)) {
            return [false, 'El archivo privado ya no estaba disponible.'];
        }

        try {
            $this->files->delete($storedPath);
            if ($this->files->exists($storedPath)) {
                throw new RuntimeException('El almacenamiento no confirmó la eliminación.');
            }

            return [true, null];
        } catch (Throwable $exception) {
            Log::warning('La carga fue eliminada, pero el archivo requiere limpieza manual.', [
                'batch_id' => $batchId,
                'exception' => $exception,
            ]);

            return [false, 'El archivo físico requiere limpieza manual.'];
        }
    }

    private function updateFileAudit(
        ConnectionInterface $connection,
        int $auditId,
        bool $fileDeleted,
        ?string $warning,
        int $batchId,
    ): void {
        try {
            $connection
                ->table(config('imports.deletion.audit_table'))
                ->where('id', $auditId)
                ->update([
                    'file_deleted' => $fileDeleted,
                    'warning' => $warning,
                ]);
        } catch (Throwable $exception) {
            Log::critical('No se pudo actualizar el resultado físico de una eliminación.', [
                'batch_id' => $batchId,
                'audit_id' => $auditId,
                'exception' => $exception,
            ]);
        }
    }

    /**
     * @return array<string, mixed>
     */
    private function auditValues(object $batch, User $user): array
    {
        return [
            'batch_id_original' => $batch->batch_id,
            'tipo' => $batch->tipo,
            'entidad' => $batch->entidad,
            'origen' => $batch->origen,
            'archivo_original' => $batch->archivo_original,
            'archivo_interno' => $batch->archivo_interno,
            'file_hash' => $batch->archivo_sha256,
            'filas_archivo' => $batch->filas_archivo,
            'filas_insertadas' => $batch->filas_insertadas,
            'filas_error' => $batch->filas_error,
            'deleted_by_user_id' => $user->getKey(),
            'deleted_by_name' => $user->name,
            'deleted_at' => now('UTC')->format('Y-m-d H:i:s'),
            'file_deleted' => false,
            'warning' => null,
        ];
    }

    /**
     * @return list<string>
     */
    private function tablesFor(string $entity): array
    {
        return $this->entityTables()[$entity];
    }

    /**
     * @return array<string, list<string>>
     */
    private function entityTables(): array
    {
        return config('imports.deletion.entity_tables', []);
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.connection'));
    }
}
