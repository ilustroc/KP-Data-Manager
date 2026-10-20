<?php

namespace App\Services\Imports;

use Illuminate\Database\ConnectionInterface;
use Illuminate\Support\Facades\DB;

final class ImportFileAccessService
{
    public function __construct(private readonly ImportFileService $files) {}

    public function prepareBatch(int $batchId): void
    {
        $relativePath = $this->connection()
            ->table(config('imports.table'))
            ->where('batch_id', $batchId)
            ->value('archivo_ruta');

        if (! is_string($relativePath) || trim($relativePath) === '') {
            throw new ImportFileAccessException('El batch no tiene un archivo privado disponible para el ETL.');
        }

        $this->prepare($relativePath);
    }

    public function prepare(string $relativePath): void
    {
        if (! $this->files->exists($relativePath)) {
            throw new ImportFileAccessException('El archivo privado del batch no existe.');
        }

        $absolutePath = realpath($this->files->disk()->path($relativePath));
        $storageRoot = realpath($this->files->disk()->path(''));

        if ($absolutePath === false
            || $storageRoot === false
            || ! is_file($absolutePath)
            || ! $this->isWithinStorageRoot($absolutePath, $storageRoot)) {
            throw new ImportFileAccessException('La ruta privada del batch no es segura.');
        }

        $sharedGroup = trim((string) config('imports.private_files.shared_group'));
        if (PHP_OS_FAMILY === 'Windows') {
            if ($sharedGroup !== '') {
                throw new ImportFileAccessException('El grupo compartido del ETL solo puede configurarse en un host POSIX.');
            }
            $this->assertReadable($absolutePath);

            return;
        }

        if ($sharedGroup === '' && (bool) config('imports.private_files.enforce_before_dispatch')) {
            throw new ImportFileAccessException('IMPORT_SHARED_GROUP es obligatorio para proteger el acceso ETL en hosts POSIX.');
        }

        $directories = $this->directoriesBetween($storageRoot, dirname($absolutePath));
        $directoryMode = (int) config('imports.private_files.directory_mode', 02750);
        $fileMode = (int) config('imports.private_files.file_mode', 0640);

        if ($sharedGroup !== '') {
            $groupId = $this->resolveSharedGroupId($sharedGroup);
            $this->assertEtlUserBelongsToGroup($sharedGroup, $groupId);

            foreach ($directories as $directory) {
                $this->ensureGroup($directory, $sharedGroup, $groupId);
            }
            $this->ensureGroup($absolutePath, $sharedGroup, $groupId);
        }

        foreach ($directories as $directory) {
            $this->ensureMode(
                $directory,
                $directoryMode,
                'No se pudieron aplicar permisos privados al directorio de importación.',
            );
        }
        $this->ensureMode(
            $absolutePath,
            $fileMode,
            'No se pudieron aplicar permisos privados al archivo de importación.',
        );

        clearstatcache(true, $absolutePath);
        $this->assertReadable($absolutePath, $sharedGroup);
    }

    private function assertReadable(string $absolutePath, string $sharedGroup = ''): void
    {
        if ($sharedGroup === '') {
            if (! is_readable($absolutePath)) {
                throw new ImportFileAccessException('El archivo privado no es legible por el proceso ETL.');
            }

            return;
        }

        $status = stat($absolutePath);
        $group = posix_getgrnam($sharedGroup);
        if ($status === false || $group === false
            || (int) $status['gid'] !== (int) $group['gid']
            || (((int) $status['mode']) & 0040) === 0) {
            throw new ImportFileAccessException('El archivo privado no concede lectura al grupo compartido del ETL.');
        }
    }

    private function resolveSharedGroupId(string $sharedGroup): int
    {
        if (! function_exists('posix_getgrnam') || ! function_exists('posix_getpwnam')) {
            throw new ImportFileAccessException('La extensión POSIX es necesaria para validar el grupo compartido del ETL.');
        }

        $group = posix_getgrnam($sharedGroup);
        if ($group === false) {
            throw new ImportFileAccessException('El grupo compartido configurado para el ETL no existe.');
        }

        return (int) $group['gid'];
    }

    private function assertEtlUserBelongsToGroup(string $sharedGroup, int $groupId): void
    {
        $etlUser = trim((string) config('imports.private_files.etl_user'));
        if ($etlUser === '') {
            throw new ImportFileAccessException('IMPORT_ETL_USER es obligatorio cuando se configura un grupo compartido.');
        }

        $user = posix_getpwnam($etlUser);
        $group = posix_getgrnam($sharedGroup);
        $isMember = $user !== false
            && $group !== false
            && ((int) $user['gid'] === $groupId || in_array($etlUser, $group['members'], true));

        if (! $isMember) {
            throw new ImportFileAccessException('El usuario ETL no pertenece al grupo compartido configurado.');
        }
    }

    private function ensureGroup(string $path, string $sharedGroup, int $groupId): void
    {
        clearstatcache(true, $path);
        $status = stat($path);
        if ($status !== false && (int) $status['gid'] === $groupId) {
            return;
        }

        if (! @chgrp($path, $sharedGroup)) {
            throw new ImportFileAccessException('No se pudo asignar el grupo compartido al almacenamiento privado.');
        }
    }

    private function ensureMode(string $path, int $mode, string $failureMessage): void
    {
        clearstatcache(true, $path);
        $status = stat($path);
        if ($status !== false && (((int) $status['mode']) & 07777) === $mode) {
            return;
        }

        if (! @chmod($path, $mode)) {
            throw new ImportFileAccessException($failureMessage);
        }
    }

    /** @return list<string> */
    private function directoriesBetween(string $storageRoot, string $leafDirectory): array
    {
        $directories = [];
        $directory = $leafDirectory;

        while ($this->isWithinStorageRoot($directory, $storageRoot)) {
            $directories[] = $directory;
            if ($directory === $storageRoot) {
                break;
            }
            $directory = dirname($directory);
        }

        return array_reverse($directories);
    }

    private function isWithinStorageRoot(string $path, string $storageRoot): bool
    {
        $normalizedRoot = rtrim(str_replace('\\', '/', $storageRoot), '/');
        $normalizedPath = str_replace('\\', '/', $path);

        return $normalizedPath === $normalizedRoot
            || str_starts_with($normalizedPath, $normalizedRoot.'/');
    }

    private function connection(): ConnectionInterface
    {
        return DB::connection(config('imports.connection'));
    }
}
