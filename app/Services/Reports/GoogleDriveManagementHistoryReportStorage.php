<?php

namespace App\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use Google\Service\Drive\DriveFile;
use Illuminate\Support\Facades\Log;
use Throwable;

class GoogleDriveManagementHistoryReportStorage implements ManagementHistoryReportStorage
{
    public function __construct(
        private readonly GoogleDriveReportConfiguration $configuration,
        private readonly GoogleDriveReportGatewayFactory $gatewayFactory,
        private readonly GoogleDriveResumableUploader $uploader,
        private readonly GoogleDriveApiErrorContext $errorContext,
    ) {}

    public function store(ManagementHistoryExport $export): StoredManagementHistoryReport
    {
        $configuration = $this->configuration->validated();
        $sizeBytes = $this->fileSize($export->path);
        $operation = 'find';
        $remoteFileId = null;
        $metadataObtained = false;
        $webViewLinkPresent = null;

        try {
            $gateway = $this->gatewayFactory->make($configuration->credentialsPath);
            $matches = $gateway->findFiles(
                $configuration->folderId,
                $configuration->filename,
                $configuration->sharedDriveId,
            );

            if (count($matches) > 1) {
                throw new ManagementHistoryReportStorageException(
                    'Se encontraron varios archivos remotos con el nombre configurado.',
                );
            }

            $operation = $matches === [] ? 'create' : 'update';
            $remoteFileId = $matches === [] ? null : $this->fileId($matches[0]);
            $request = $matches === []
                ? $gateway->createUploadRequest($configuration->folderId, $configuration->filename)
                : $gateway->updateUploadRequest($remoteFileId, $configuration->filename);
            $operation = 'upload';
            $storedFile = $this->uploader->upload(
                client: $gateway->client(),
                request: $request,
                path: $export->path,
                sizeBytes: $sizeBytes,
                chunkSizeBytes: $configuration->chunkSizeBytes,
            );
            $uploadedFileId = $this->fileId($storedFile);

            if ($remoteFileId !== null && $uploadedFileId !== $remoteFileId) {
                throw new ManagementHistoryReportStorageException(
                    'Google Drive devolvió un identificador distinto al archivo actualizado.',
                );
            }

            $remoteFileId = $uploadedFileId;
            $operation = 'metadata';
            $metadata = $gateway->getFileMetadata($remoteFileId);
            $metadataObtained = true;
            $metadataFileId = $this->fileId($metadata);

            if ($metadataFileId !== $remoteFileId) {
                throw new ManagementHistoryReportStorageException(
                    'Google Drive devolvió metadata de un archivo distinto al almacenado.',
                );
            }

            $webViewLinkPresent = trim((string) $metadata->getWebViewLink()) !== '';

            return new StoredManagementHistoryReport(
                fileId: $remoteFileId,
                filename: $configuration->filename,
                webViewLink: $this->webViewLink($metadata),
                sizeBytes: $sizeBytes,
            );
        } catch (ManagementHistoryReportStorageException $exception) {
            $this->logFailure(
                $exception,
                $operation,
                $remoteFileId,
                $configuration->sharedDriveId !== null,
                $metadataObtained,
                $webViewLinkPresent,
            );

            throw $exception;
        } catch (Throwable $exception) {
            $this->logFailure(
                $exception,
                $operation,
                $remoteFileId,
                $configuration->sharedDriveId !== null,
                $metadataObtained,
                $webViewLinkPresent,
            );

            throw new ManagementHistoryReportStorageException(
                'Google Drive no pudo almacenar el reporte.',
                previous: $exception,
            );
        }
    }

    private function logFailure(
        Throwable $exception,
        string $operation,
        ?string $fileId,
        bool $sharedDriveConfigured,
        bool $metadataObtained,
        ?bool $webViewLinkPresent,
    ): void {
        $context = $this->errorContext->build(
            exception: $exception,
            operation: $operation,
            fileId: $fileId,
            sharedDriveConfigured: $sharedDriveConfigured,
        );
        $context['metadata_obtained'] = $metadataObtained;
        $context['web_view_link_present'] = $webViewLinkPresent;

        Log::error('management_history_drive_storage_failed', $context);
    }

    private function fileSize(string $path): int
    {
        $size = @filesize($path);

        if ($size === false || $size <= 0) {
            throw new ManagementHistoryReportStorageException(
                'El reporte temporal no está disponible para su almacenamiento.',
            );
        }

        return $size;
    }

    private function fileId(DriveFile $file): string
    {
        $fileId = trim((string) $file->getId());

        if ($fileId === '') {
            throw new ManagementHistoryReportStorageException(
                'Google Drive no devolvió un identificador válido para el reporte.',
            );
        }

        return $fileId;
    }

    private function webViewLink(DriveFile $file): string
    {
        $webViewLink = trim((string) $file->getWebViewLink());

        if (filter_var($webViewLink, FILTER_VALIDATE_URL) === false
            || parse_url($webViewLink, PHP_URL_SCHEME) !== 'https') {
            throw new ManagementHistoryReportStorageException(
                'Google Drive no devolvió un enlace privado válido para el reporte.',
            );
        }

        return $webViewLink;
    }
}
