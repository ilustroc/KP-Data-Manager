<?php

namespace Tests\Unit\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use App\Services\Reports\GoogleDriveReportConfiguration;
use Tests\TestCase;

class GoogleDriveReportConfigurationTest extends TestCase
{
    public function test_returns_validated_drive_settings(): void
    {
        $credentialsPath = tempnam(sys_get_temp_dir(), 'kpdm-google-credentials-');
        $this->assertIsString($credentialsPath);
        config([
            'reports.management_history.drive.enabled' => true,
            'reports.management_history.drive.credentials_path' => $credentialsPath,
            'reports.management_history.drive.folder_id' => 'reports-folder-id',
            'reports.management_history.drive.shared_drive_id' => 'shared-drive-id',
            'reports.management_history.drive.filename' => 'historico_gestiones.xlsx',
            'reports.management_history.drive.chunk_size_bytes' => 5 * 1024 * 1024,
        ]);

        try {
            $settings = (new GoogleDriveReportConfiguration)->validated();

            $this->assertSame($credentialsPath, $settings->credentialsPath);
            $this->assertSame('reports-folder-id', $settings->folderId);
            $this->assertSame('shared-drive-id', $settings->sharedDriveId);
            $this->assertSame('historico_gestiones.xlsx', $settings->filename);
            $this->assertSame(5 * 1024 * 1024, $settings->chunkSizeBytes);
        } finally {
            @unlink($credentialsPath);
        }
    }

    public function test_rejects_disabled_drive_configuration(): void
    {
        config(['reports.management_history.drive.enabled' => false]);

        $this->expectException(ManagementHistoryReportStorageException::class);
        $this->expectExceptionMessage('no está habilitado');

        (new GoogleDriveReportConfiguration)->validated();
    }

    public function test_access_validation_does_not_require_upload_options(): void
    {
        $credentialsPath = tempnam(sys_get_temp_dir(), 'kpdm-google-credentials-');
        $this->assertIsString($credentialsPath);
        config([
            'reports.management_history.drive.enabled' => true,
            'reports.management_history.drive.credentials_path' => $credentialsPath,
            'reports.management_history.drive.folder_id' => 'reports-folder-id',
            'reports.management_history.drive.shared_drive_id' => '',
            'reports.management_history.drive.filename' => '',
            'reports.management_history.drive.chunk_size_bytes' => 0,
        ]);

        try {
            $settings = (new GoogleDriveReportConfiguration)->validatedAccess();

            $this->assertSame('reports-folder-id', $settings->folderId);
            $this->assertNull($settings->sharedDriveId);
        } finally {
            @unlink($credentialsPath);
        }
    }

    public function test_rejects_missing_credentials_without_exposing_path(): void
    {
        config([
            'reports.management_history.drive.enabled' => true,
            'reports.management_history.drive.credentials_path' => 'C:\\private\\google\\secret-service-account.json',
            'reports.management_history.drive.folder_id' => 'reports-folder-id',
            'reports.management_history.drive.filename' => 'historico_gestiones.xlsx',
            'reports.management_history.drive.chunk_size_bytes' => 5 * 1024 * 1024,
        ]);

        try {
            (new GoogleDriveReportConfiguration)->validated();
            $this->fail('Se esperaba un error de credenciales no disponibles.');
        } catch (ManagementHistoryReportStorageException $exception) {
            $this->assertSame('El archivo de credenciales de Google Drive no está disponible.', $exception->getMessage());
            $this->assertStringNotContainsString('secret-service-account.json', $exception->getMessage());
        }
    }
}
