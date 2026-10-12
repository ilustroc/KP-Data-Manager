<?php

namespace Tests\Unit\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use App\Services\Reports\GoogleDriveApiErrorContext;
use App\Services\Reports\GoogleDriveManagementHistoryReportStorage;
use App\Services\Reports\GoogleDriveReportConfiguration;
use App\Services\Reports\GoogleDriveReportGateway;
use App\Services\Reports\GoogleDriveReportGatewayFactory;
use App\Services\Reports\GoogleDriveResumableUploader;
use App\Services\Reports\ManagementHistoryExport;
use Google\Client;
use Google\Service\Drive\DriveFile;
use Google\Service\Exception as GoogleServiceException;
use Illuminate\Support\Facades\Log;
use Mockery;
use Psr\Http\Message\RequestInterface;
use Tests\TestCase;

class GoogleDriveManagementHistoryReportStorageTest extends TestCase
{
    public function test_creates_remote_file_when_no_matching_file_exists(): void
    {
        [$credentialsPath, $reportPath] = $this->temporaryFiles();
        $this->configureDrive($credentialsPath, 'shared-drive-id');
        $client = Mockery::mock(Client::class);
        $request = Mockery::mock(RequestInterface::class);
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('findFiles')
            ->once()
            ->with('reports-folder-id', 'historico_gestiones.xlsx', 'shared-drive-id')
            ->andReturn([]);
        $gateway->shouldReceive('createUploadRequest')
            ->once()
            ->with('reports-folder-id', 'historico_gestiones.xlsx')
            ->andReturn($request);
        $gateway->shouldReceive('updateUploadRequest')->never();
        $gateway->shouldReceive('client')->once()->andReturn($client);
        $gateway->shouldReceive('getFileMetadata')
            ->once()
            ->with('new-file-id')
            ->andReturn($this->driveFile('new-file-id'));
        $gateway->shouldReceive('trashFile')->never();
        $gateway->shouldReceive('deleteFile')->never();
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->with($credentialsPath)->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')
            ->once()
            ->with($client, $request, $reportPath, 20, 5 * 1024 * 1024)
            ->andReturn(new DriveFile(['id' => 'new-file-id']));

        try {
            $stored = (new GoogleDriveManagementHistoryReportStorage(new GoogleDriveReportConfiguration, $factory, $uploader, new GoogleDriveApiErrorContext))->store(
                new ManagementHistoryExport($reportPath, 'historico_gestiones_20261008.xlsx', 360832),
            );

            $this->assertSame('new-file-id', $stored->fileId);
            $this->assertSame('historico_gestiones.xlsx', $stored->filename);
            $this->assertSame('https://drive.google.com/file/d/new-file-id/view', $stored->webViewLink);
            $this->assertSame(20, $stored->sizeBytes);
            $this->assertFileExists($reportPath);
        } finally {
            @unlink($credentialsPath);
            @unlink($reportPath);
        }
    }

    public function test_updates_only_matching_remote_file_when_exactly_one_exists(): void
    {
        [$credentialsPath, $reportPath] = $this->temporaryFiles();
        $this->configureDrive($credentialsPath);
        $client = Mockery::mock(Client::class);
        $request = Mockery::mock(RequestInterface::class);
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('findFiles')
            ->once()
            ->andReturn([$this->driveFile('existing-file-id')]);
        $gateway->shouldReceive('createUploadRequest')->never();
        $gateway->shouldReceive('updateUploadRequest')
            ->once()
            ->with('existing-file-id', 'historico_gestiones.xlsx')
            ->andReturn($request);
        $gateway->shouldReceive('client')->once()->andReturn($client);
        $gateway->shouldReceive('getFileMetadata')
            ->once()
            ->with('existing-file-id')
            ->andReturn($this->driveFile('existing-file-id'));
        $gateway->shouldReceive('trashFile')->never();
        $gateway->shouldReceive('deleteFile')->never();
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')
            ->once()
            ->andReturn(new DriveFile(['id' => 'existing-file-id']));

        try {
            $stored = (new GoogleDriveManagementHistoryReportStorage(new GoogleDriveReportConfiguration, $factory, $uploader, new GoogleDriveApiErrorContext))->store(
                new ManagementHistoryExport($reportPath, 'historico_gestiones_20261008.xlsx', 360832),
            );

            $this->assertSame('existing-file-id', $stored->fileId);
            $this->assertSame('https://drive.google.com/file/d/existing-file-id/view', $stored->webViewLink);
        } finally {
            @unlink($credentialsPath);
            @unlink($reportPath);
        }
    }

    public function test_rejects_multiple_matching_remote_files_without_uploading(): void
    {
        [$credentialsPath, $reportPath] = $this->temporaryFiles();
        $this->configureDrive($credentialsPath);
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('findFiles')
            ->once()
            ->andReturn([$this->driveFile('first-id'), $this->driveFile('second-id')]);
        $gateway->shouldReceive('createUploadRequest')->never();
        $gateway->shouldReceive('updateUploadRequest')->never();
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldNotReceive('upload');

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);
            $this->expectExceptionMessage('varios archivos remotos');

            (new GoogleDriveManagementHistoryReportStorage(new GoogleDriveReportConfiguration, $factory, $uploader, new GoogleDriveApiErrorContext))->store(
                new ManagementHistoryExport($reportPath, 'historico_gestiones_20261008.xlsx', 360832),
            );
        } finally {
            @unlink($credentialsPath);
            @unlink($reportPath);
        }
    }

    public function test_missing_drive_configuration_fails_before_creating_client(): void
    {
        config(['reports.management_history.drive.enabled' => false]);
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldNotReceive('make');
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldNotReceive('upload');

        $this->expectException(ManagementHistoryReportStorageException::class);
        $this->expectExceptionMessage('no está habilitado');

        (new GoogleDriveManagementHistoryReportStorage(new GoogleDriveReportConfiguration, $factory, $uploader, new GoogleDriveApiErrorContext))->store(
            new ManagementHistoryExport('unused.xlsx', 'unused.xlsx', 0),
        );
    }

    public function test_missing_credentials_file_fails_without_exposing_configured_path(): void
    {
        config([
            'reports.management_history.drive.enabled' => true,
            'reports.management_history.drive.credentials_path' => 'C:\\private\\google\\secret-service-account.json',
            'reports.management_history.drive.folder_id' => 'reports-folder-id',
            'reports.management_history.drive.filename' => 'historico_gestiones.xlsx',
            'reports.management_history.drive.chunk_size_bytes' => 5 * 1024 * 1024,
        ]);
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldNotReceive('make');
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);

        try {
            (new GoogleDriveManagementHistoryReportStorage(new GoogleDriveReportConfiguration, $factory, $uploader, new GoogleDriveApiErrorContext))->store(
                new ManagementHistoryExport('unused.xlsx', 'unused.xlsx', 0),
            );
            $this->fail('Se esperaba un error de credenciales no disponibles.');
        } catch (ManagementHistoryReportStorageException $exception) {
            $this->assertSame('El archivo de credenciales de Google Drive no está disponible.', $exception->getMessage());
            $this->assertStringNotContainsString('secret-service-account.json', $exception->getMessage());
        }
    }

    public function test_logs_google_api_reason_before_wrapping_upload_failure(): void
    {
        [$credentialsPath, $reportPath] = $this->temporaryFiles();
        $this->configureDrive($credentialsPath, 'shared-drive-id');
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('findFiles')->once()->andReturn([]);
        $gateway->shouldReceive('createUploadRequest')->once()->andReturn(Mockery::mock(RequestInterface::class));
        $gateway->shouldReceive('client')->once()->andReturn(Mockery::mock(Client::class));
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')->once()->andThrow(new GoogleServiceException(
            'private_key=secret access_token=secret-token',
            403,
            null,
            [['reason' => 'storageQuotaExceeded', 'domain' => 'usageLimits']],
        ));
        Log::shouldReceive('error')
            ->once()
            ->with('management_history_drive_storage_failed', Mockery::on(function (array $context): bool {
                $serialized = json_encode($context, JSON_THROW_ON_ERROR);

                return $context['operation'] === 'upload'
                    && $context['status_code'] === 403
                    && $context['google_api_reasons'] === ['storageQuotaExceeded']
                    && ! str_contains($serialized, 'secret-token')
                    && ! str_contains($serialized, 'private_key=secret');
            }));

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);

            (new GoogleDriveManagementHistoryReportStorage(new GoogleDriveReportConfiguration, $factory, $uploader, new GoogleDriveApiErrorContext))->store(
                new ManagementHistoryExport($reportPath, 'historico_gestiones_20261008.xlsx', 360832),
            );
        } finally {
            @unlink($credentialsPath);
            @unlink($reportPath);
        }
    }

    public function test_rejects_empty_web_view_link_returned_by_refreshed_metadata(): void
    {
        [$credentialsPath, $reportPath] = $this->temporaryFiles();
        $this->configureDrive($credentialsPath);
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('findFiles')->once()->andReturn([]);
        $gateway->shouldReceive('createUploadRequest')->once()->andReturn(Mockery::mock(RequestInterface::class));
        $gateway->shouldReceive('client')->once()->andReturn(Mockery::mock(Client::class));
        $gateway->shouldReceive('getFileMetadata')
            ->once()
            ->with('new-file-id')
            ->andReturn(new DriveFile(['id' => 'new-file-id']));
        $gateway->shouldReceive('trashFile')->never();
        $gateway->shouldReceive('deleteFile')->never();
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')
            ->once()
            ->andReturn(new DriveFile(['id' => 'new-file-id']));
        Log::shouldReceive('error')
            ->once()
            ->with('management_history_drive_storage_failed', Mockery::on(function (array $context): bool {
                $serialized = json_encode($context, JSON_THROW_ON_ERROR);

                return $context['operation'] === 'metadata'
                    && $context['metadata_obtained'] === true
                    && $context['web_view_link_present'] === false
                    && is_string($context['file_reference'])
                    && ! str_contains($serialized, 'new-file-id');
            }));

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);
            $this->expectExceptionMessage('enlace privado válido');

            (new GoogleDriveManagementHistoryReportStorage(new GoogleDriveReportConfiguration, $factory, $uploader, new GoogleDriveApiErrorContext))->store(
                new ManagementHistoryExport($reportPath, 'historico_gestiones_20261008.xlsx', 360832),
            );
        } finally {
            @unlink($credentialsPath);
            @unlink($reportPath);
        }
    }

    public function test_rejects_non_https_web_view_link_returned_by_refreshed_metadata(): void
    {
        [$credentialsPath, $reportPath] = $this->temporaryFiles();
        $this->configureDrive($credentialsPath);
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('findFiles')->once()->andReturn([$this->driveFile('existing-file-id')]);
        $gateway->shouldReceive('updateUploadRequest')->once()->andReturn(Mockery::mock(RequestInterface::class));
        $gateway->shouldReceive('client')->once()->andReturn(Mockery::mock(Client::class));
        $gateway->shouldReceive('getFileMetadata')
            ->once()
            ->with('existing-file-id')
            ->andReturn(new DriveFile([
                'id' => 'existing-file-id',
                'webViewLink' => 'http://drive.google.com/file/d/existing-file-id/view',
            ]));
        $gateway->shouldReceive('trashFile')->never();
        $gateway->shouldReceive('deleteFile')->never();
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')
            ->once()
            ->andReturn(new DriveFile(['id' => 'existing-file-id']));

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);
            $this->expectExceptionMessage('enlace privado válido');

            (new GoogleDriveManagementHistoryReportStorage(new GoogleDriveReportConfiguration, $factory, $uploader, new GoogleDriveApiErrorContext))->store(
                new ManagementHistoryExport($reportPath, 'historico_gestiones_20261008.xlsx', 360832),
            );
        } finally {
            @unlink($credentialsPath);
            @unlink($reportPath);
        }
    }

    /** @return array{string, string} */
    private function temporaryFiles(): array
    {
        $credentialsPath = tempnam(sys_get_temp_dir(), 'kpdm-google-credentials-');
        $reportPath = tempnam(sys_get_temp_dir(), 'kpdm-google-report-');
        $this->assertIsString($credentialsPath);
        $this->assertIsString($reportPath);
        file_put_contents($credentialsPath, '{}');
        file_put_contents($reportPath, '12345678901234567890');

        return [$credentialsPath, $reportPath];
    }

    private function configureDrive(string $credentialsPath, string $sharedDriveId = ''): void
    {
        config([
            'reports.management_history.drive.enabled' => true,
            'reports.management_history.drive.credentials_path' => $credentialsPath,
            'reports.management_history.drive.folder_id' => 'reports-folder-id',
            'reports.management_history.drive.shared_drive_id' => $sharedDriveId,
            'reports.management_history.drive.filename' => 'historico_gestiones.xlsx',
            'reports.management_history.drive.chunk_size_bytes' => 5 * 1024 * 1024,
        ]);
    }

    private function driveFile(string $fileId): DriveFile
    {
        return new DriveFile([
            'id' => $fileId,
            'name' => 'historico_gestiones.xlsx',
            'size' => '20',
            'webViewLink' => "https://drive.google.com/file/d/{$fileId}/view",
        ]);
    }
}
