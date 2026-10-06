<?php

namespace App\Console\Commands;

use App\FinancialEntity;
use App\ImportOrigin;
use App\ImportType;
use App\Services\Imports\DuplicateImportFile;
use App\Services\Imports\ImportRegistrationFailed;
use App\Services\Imports\ImportUploadService;
use App\Services\Imports\InvalidImportFile;
use Illuminate\Console\Command;
use ValueError;

class RegisterImport extends Command
{
    protected $signature = 'kpdm:import:register
        {--file= : Archivo relativo al inbox configurado}
        {--tipo=PAGOS : Tipo de carga}
        {--entidad= : Entidad financiera para cargas de cartera}
        {--origen=HISTORICO : Origen de la carga}';

    protected $description = 'Registra sin procesar un archivo grande ubicado en el inbox privado';

    public function handle(ImportUploadService $uploads): int
    {
        $fileOption = trim((string) $this->option('file'));

        if ($fileOption === '') {
            $this->error('Debes indicar --file con una ruta relativa al inbox.');

            return self::FAILURE;
        }

        try {
            $type = ImportType::from(strtoupper((string) $this->option('tipo')));
            $origin = ImportOrigin::from(strtoupper((string) $this->option('origen')));
            $entity = $this->resolveEntity($type);
            $sourcePath = $this->resolveInboxFile($fileOption);
            $batchId = $uploads->registerInbox(
                sourcePath: $sourcePath,
                originalName: basename($sourcePath),
                type: $type,
                origin: $origin,
                entity: $entity,
                auditor: $this->commandAuditor(),
            );
        } catch (ValueError) {
            $this->error('El tipo u origen indicado no es válido.');

            return self::FAILURE;
        } catch (DuplicateImportFile|InvalidImportFile|ImportRegistrationFailed $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }

        $this->info("Batch #{$batchId} registrado en estado PENDIENTE.");

        return self::SUCCESS;
    }

    private function resolveEntity(ImportType $type): ?FinancialEntity
    {
        $entityOption = strtoupper(trim((string) $this->option('entidad')));

        if ($type !== ImportType::Portfolio) {
            if ($entityOption !== '') {
                throw new ValueError('La entidad solo corresponde a cargas de cartera.');
            }

            return null;
        }

        $entity = FinancialEntity::tryFrom($entityOption);

        if ($entity === null || ! $entity->isImplemented()) {
            throw new ValueError('La carga de cartera requiere una entidad con perfil implementado.');
        }

        return $entity;
    }

    private function resolveInboxFile(string $relativePath): string
    {
        if ($this->isAbsolutePath($relativePath)) {
            throw new InvalidImportFile('Solo se aceptan rutas relativas dentro del inbox configurado.');
        }

        $segments = preg_split('/[\\\\\/]+/', $relativePath) ?: [];

        if (in_array('..', $segments, true)) {
            throw new InvalidImportFile('La ruta indicada intenta salir del inbox configurado.');
        }

        $inbox = realpath((string) config('imports.inbox_path'));

        if ($inbox === false || ! is_dir($inbox)) {
            throw new InvalidImportFile('El inbox configurado no existe o no es accesible.');
        }

        $normalizedRelativePath = str_replace(['/', '\\'], DIRECTORY_SEPARATOR, $relativePath);
        $candidate = realpath($inbox.DIRECTORY_SEPARATOR.$normalizedRelativePath);

        if ($candidate === false || ! is_file($candidate)) {
            throw new InvalidImportFile('El archivo indicado no existe dentro del inbox.');
        }

        $inboxPrefix = rtrim($inbox, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR;
        $candidateForComparison = $candidate;

        if (DIRECTORY_SEPARATOR === '\\') {
            $inboxPrefix = mb_strtolower($inboxPrefix);
            $candidateForComparison = mb_strtolower($candidateForComparison);
        }

        if (! str_starts_with($candidateForComparison, $inboxPrefix)) {
            throw new InvalidImportFile('La ruta indicada intenta salir del inbox configurado.');
        }

        return $candidate;
    }

    private function isAbsolutePath(string $path): bool
    {
        return preg_match('/^(?:[A-Za-z]:[\\\\\/]|[\\\\\/]{1,2})/', $path) === 1;
    }

    private function commandAuditor(): string
    {
        $user = getenv('USERNAME') ?: getenv('USER') ?: get_current_user();

        return 'cli:'.mb_substr((string) $user, 0, 96);
    }
}
