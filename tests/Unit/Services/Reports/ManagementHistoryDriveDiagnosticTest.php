<?php

namespace Tests\Unit\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use App\Services\Reports\GoogleDriveReportConfiguration;
use App\Services\Reports\GoogleDriveReportGateway;
use App\Services\Reports\GoogleDriveReportGatewayFactory;
use App\Services\Reports\ManagementHistoryDriveDiagnostic;
use Google\Service\Drive\Drive as SharedDrive;
use Google\Service\Drive\DriveFile;
use Illuminate\Support\Facades\Log;
use Mockery;
use RuntimeException;
use Tests\TestCase;

class ManagementHistoryDriveDiagnosticTest extends TestCase
{
    public function test_validates_authentication_shared_drive_and_destination_folder(): void
    {
        $credentialsPath = $this->configureDrive();
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('authenticateServiceAccount')->once();
        $gateway->shouldReceive('getSharedDrive')
            ->once()
            ->with('shared-drive-id')
            ->andReturn(new SharedDrive(['id' => 'shared-drive-id']));
        $gateway->shouldReceive('getFolder')
            ->once()
            ->with('reports-folder-id')
            ->andReturn($this->folder());
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->with($credentialsPath)->andReturn($gateway);
        $progress = [];

        try {
            $result = (new ManagementHistoryDriveDiagnostic(
                new GoogleDriveReportConfiguration,
                $factory,
            ))->run(function (string $message) use (&$progress): void {
                $progress[] = $message;
            });

            $this->assertTrue($result->sharedDriveConfigured);
            $this->assertSame([
                '[1/4] Validando configuración...',
                '[2/4] Autenticando con Google Drive...',
                '[3/4] Verificando Unidad compartida...',
                '[4/4] Verificando carpeta destino...',
            ], $progress);
        } finally {
            @unlink($credentialsPath);
        }
    }

    public function test_rejects_folder_outside_configured_shared_drive(): void
    {
        $credentialsPath = $this->configureDrive();
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('authenticateServiceAccount')->once();
        $gateway->shouldReceive('getSharedDrive')->once()->andReturn(new SharedDrive(['id' => 'shared-drive-id']));
        $gateway->shouldReceive('getFolder')->once()->andReturn($this->folder('different-drive-id'));
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        Log::shouldReceive('error')
            ->once()
            ->with('management_history_drive_diagnostic_failed', Mockery::on(
                fn (array $context): bool => $context['stage'] === 'folder'
                    && ! array_key_exists('message', $context),
            ));

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);
            $this->expectExceptionMessage('no pertenece');

            (new ManagementHistoryDriveDiagnostic(new GoogleDriveReportConfiguration, $factory))->run();
        } finally {
            @unlink($credentialsPath);
        }
    }

    public function test_authentication_failure_is_logged_without_secrets(): void
    {
        $credentialsPath = $this->configureDrive();
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('authenticateServiceAccount')
            ->once()
            ->andThrow(new RuntimeException('private_key=secret access_token=secret-token'));
        $gateway->shouldNotReceive('getSharedDrive');
        $gateway->shouldNotReceive('getFolder');
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        Log::shouldReceive('error')
            ->once()
            ->with('management_history_drive_diagnostic_failed', Mockery::on(function (array $context): bool {
                $serialized = json_encode($context);

                return $context['stage'] === 'authentication'
                    && is_string($serialized)
                    && ! str_contains($serialized, 'secret')
                    && ! str_contains($serialized, 'token');
            }));

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);
            $this->expectExceptionMessage('No fue posible validar el acceso');

            (new ManagementHistoryDriveDiagnostic(new GoogleDriveReportConfiguration, $factory))->run();
        } finally {
            @unlink($credentialsPath);
        }
    }

    public function test_rejects_trashed_destination_folder(): void
    {
        $credentialsPath = $this->configureDrive();
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('authenticateServiceAccount')->once();
        $gateway->shouldReceive('getSharedDrive')->once()->andReturn(new SharedDrive(['id' => 'shared-drive-id']));
        $folder = $this->folder();
        $folder->setTrashed(true);
        $gateway->shouldReceive('getFolder')->once()->andReturn($folder);
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        Log::shouldReceive('error')->once();

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);
            $this->expectExceptionMessage('no está disponible');

            (new ManagementHistoryDriveDiagnostic(new GoogleDriveReportConfiguration, $factory))->run();
        } finally {
            @unlink($credentialsPath);
        }
    }

    private function configureDrive(): string
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

        return $credentialsPath;
    }

    private function folder(string $driveId = 'shared-drive-id'): DriveFile
    {
        return new DriveFile([
            'id' => 'reports-folder-id',
            'mimeType' => 'application/vnd.google-apps.folder',
            'trashed' => false,
            'driveId' => $driveId,
        ]);
    }
}
