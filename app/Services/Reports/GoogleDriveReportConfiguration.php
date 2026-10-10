<?php

namespace App\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;

class GoogleDriveReportConfiguration
{
    public function validated(): GoogleDriveReportSettings
    {
        $access = $this->validatedAccess();
        $filename = trim((string) config('reports.management_history.drive.filename', ''));
        $chunkSizeBytes = (int) config('reports.management_history.drive.chunk_size_bytes', 0);

        if ($filename === '' || basename($filename) !== $filename || preg_match('/[\x00-\x1F]/', $filename)) {
            throw new ManagementHistoryReportStorageException(
                'El nombre remoto del reporte no es válido.',
            );
        }

        if ($chunkSizeBytes <= 0) {
            throw new ManagementHistoryReportStorageException(
                'El tamaño de bloque para Google Drive no es válido.',
            );
        }

        return new GoogleDriveReportSettings(
            credentialsPath: $access->credentialsPath,
            folderId: $access->folderId,
            sharedDriveId: $access->sharedDriveId,
            filename: $filename,
            chunkSizeBytes: $chunkSizeBytes,
        );
    }

    public function validatedAccess(): GoogleDriveReportAccessSettings
    {
        if (! (bool) config('reports.management_history.drive.enabled', false)) {
            throw new ManagementHistoryReportStorageException(
                'Google Drive no está habilitado para el reporte.',
            );
        }

        $credentialsPath = trim((string) config('reports.management_history.drive.credentials_path', ''));
        $folderId = trim((string) config('reports.management_history.drive.folder_id', ''));
        $sharedDriveId = trim((string) config('reports.management_history.drive.shared_drive_id', ''));

        if ($credentialsPath === '') {
            throw new ManagementHistoryReportStorageException(
                'Las credenciales de Google Drive no están configuradas.',
            );
        }

        if (! is_file($credentialsPath) || ! is_readable($credentialsPath)) {
            throw new ManagementHistoryReportStorageException(
                'El archivo de credenciales de Google Drive no está disponible.',
            );
        }

        if ($folderId === '') {
            throw new ManagementHistoryReportStorageException(
                'La carpeta de Google Drive no está configurada.',
            );
        }

        return new GoogleDriveReportAccessSettings(
            credentialsPath: $credentialsPath,
            folderId: $folderId,
            sharedDriveId: $sharedDriveId === '' ? null : $sharedDriveId,
        );
    }
}
