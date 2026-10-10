<?php

namespace App\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use Closure;
use Illuminate\Support\Facades\Log;
use RuntimeException;
use Throwable;

class ManagementHistoryDriveUploadDiagnostic
{
    private const CONTENT = 'KP Data Manager Drive write test';

    private const MIME_TYPE = 'text/plain';

    private const REMOTE_FILENAME = 'kp_data_manager_drive_write_test.txt';

    public function __construct(
        private readonly GoogleDriveReportConfiguration $configuration,
        private readonly GoogleDriveReportGatewayFactory $gatewayFactory,
        private readonly GoogleDriveResumableUploader $uploader,
        private readonly GoogleDriveApiErrorContext $errorContext,
    ) {}

    public function run(?Closure $progress = null): ManagementHistoryDriveUploadDiagnosticResult
    {
        $operation = 'configuration';
        $settings = null;
        $gateway = null;
        $localPath = null;
        $remoteFileId = null;

        try {
            $progress?->__invoke('[1/5] Validando configuración...');
            $settings = $this->configuration->validated();

            $operation = 'local_file';
            $progress?->__invoke('[2/5] Creando archivo temporal...');
            $localPath = $this->createTemporaryFile();

            $gateway = $this->gatewayFactory->make($settings->credentialsPath);

            $operation = 'create';
            $progress?->__invoke('[3/5] Probando escritura en Google Drive...');
            $request = $gateway->createUploadRequest($settings->folderId, self::REMOTE_FILENAME);

            $operation = 'upload';
            $storedFile = $this->uploader->upload(
                client: $gateway->client(),
                request: $request,
                path: $localPath,
                sizeBytes: $this->fileSize($localPath),
                chunkSizeBytes: $settings->chunkSizeBytes,
                mimeType: self::MIME_TYPE,
            );
            $remoteFileId = trim((string) $storedFile->getId());

            if ($remoteFileId === '') {
                throw new RuntimeException('Google Drive no devolvió un identificador para el archivo de prueba.');
            }

            $operation = 'metadata';
            $progress?->__invoke('[4/5] Verificando archivo remoto...');
            $metadata = $gateway->getFileMetadata($remoteFileId);

            if (trim((string) $metadata->getId()) !== $remoteFileId
                || $metadata->getName() !== self::REMOTE_FILENAME
                || $metadata->getTrashed() === true) {
                throw new RuntimeException('Google Drive no devolvió metadata válida para el archivo de prueba.');
            }

            $capabilities = $metadata->getCapabilities();
            $canTrash = $capabilities?->getCanTrash();
            $canDelete = $capabilities?->getCanDelete();

            $operation = 'trash';
            $progress?->__invoke('[5/5] Moviendo archivo de prueba a la papelera...');
            $gateway->trashFile($remoteFileId);
            $remoteFileId = null;

            return new ManagementHistoryDriveUploadDiagnosticResult(
                created: true,
                read: true,
                trashed: true,
                canTrash: is_bool($canTrash) ? $canTrash : null,
                canDelete: is_bool($canDelete) ? $canDelete : null,
            );
        } catch (Throwable $exception) {
            Log::error('management_history_drive_upload_test_failed', $this->errorContext->build(
                exception: $exception,
                operation: $operation,
                fileId: $remoteFileId,
                sharedDriveConfigured: $settings?->sharedDriveId !== null,
            ));

            throw new ManagementHistoryReportStorageException(
                'No fue posible escribir en Google Drive.',
                previous: $exception,
            );
        } finally {
            try {
                if ($remoteFileId !== null && $gateway !== null) {
                    try {
                        $gateway->trashFile($remoteFileId);
                    } catch (Throwable $cleanupException) {
                        Log::error('management_history_drive_upload_test_cleanup_failed', $this->errorContext->build(
                            exception: $cleanupException,
                            operation: 'trash',
                            fileId: $remoteFileId,
                            sharedDriveConfigured: $settings?->sharedDriveId !== null,
                        ));
                    }
                }
            } finally {
                $this->deleteTemporaryFile($localPath);
            }
        }
    }

    private function createTemporaryFile(): string
    {
        $rootDirectory = (string) config(
            'reports.management_history.temporary_directory',
            storage_path('app/private/reports'),
        );
        $directory = $rootDirectory.DIRECTORY_SEPARATOR.'drive-write-test-'.bin2hex(random_bytes(16));

        if (! mkdir($directory, 0750, true) && ! is_dir($directory)) {
            throw new RuntimeException('No fue posible crear el directorio temporal de diagnóstico.');
        }

        $path = $directory.DIRECTORY_SEPARATOR.self::REMOTE_FILENAME;

        if (file_put_contents($path, self::CONTENT) !== strlen(self::CONTENT)) {
            $this->deleteTemporaryFile($path);

            throw new RuntimeException('No fue posible crear el archivo temporal de diagnóstico.');
        }

        return $path;
    }

    private function fileSize(string $path): int
    {
        $size = @filesize($path);

        if ($size === false || $size <= 0) {
            throw new RuntimeException('El archivo temporal de diagnóstico no está disponible.');
        }

        return $size;
    }

    private function deleteTemporaryFile(?string $path): void
    {
        if ($path === null) {
            return;
        }

        if (is_file($path)) {
            @unlink($path);
        }

        $directory = dirname($path);

        if (is_dir($directory) && (scandir($directory) ?: []) === ['.', '..']) {
            @rmdir($directory);
        }
    }
}
