<?php

namespace Tests\Unit\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use App\Services\Reports\GoogleDriveApiErrorContext;
use App\Services\Reports\GoogleDriveReportConfiguration;
use App\Services\Reports\GoogleDriveReportGateway;
use App\Services\Reports\GoogleDriveReportGatewayFactory;
use App\Services\Reports\GoogleDriveResumableUploader;
use App\Services\Reports\ManagementHistoryDriveUploadDiagnostic;
use Google\Client;
use Google\Service\Drive\DriveFile;
use Google\Service\Drive\DriveFileCapabilities;
use Google\Service\Exception as GoogleServiceException;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;
use Mockery;
use Psr\Http\Message\RequestInterface;
use RuntimeException;
use Tests\TestCase;

class ManagementHistoryDriveUploadDiagnosticTest extends TestCase
{
    public function test_creates_reads_and_moves_remote_test_file_to_trash(): void
    {
        [$credentialsPath, $temporaryRoot] = $this->configureDrive();
        Mail::fake();
        DB::shouldReceive('connection')->never();
        $client = Mockery::mock(Client::class);
        $request = Mockery::mock(RequestInterface::class);
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('createUploadRequest')
            ->once()
            ->with('reports-folder-id', 'kp_data_manager_drive_write_test.txt')
            ->andReturn($request);
        $gateway->shouldReceive('client')->once()->andReturn($client);
        $gateway->shouldReceive('getFileMetadata')
            ->once()
            ->with('test-file-id')
            ->andReturn($this->remoteFile());
        $gateway->shouldReceive('trashFile')->once()->with('test-file-id');
        $gateway->shouldNotReceive('deleteFile');
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->with($credentialsPath)->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')
            ->once()
            ->withArgs(function (
                Client $actualClient,
                RequestInterface $actualRequest,
                string $path,
                int $sizeBytes,
                int $chunkSizeBytes,
                string $mimeType,
            ) use ($client, $request): bool {
                return $actualClient === $client
                    && $actualRequest === $request
                    && file_get_contents($path) === 'KP Data Manager Drive write test'
                    && $sizeBytes === 32
                    && $chunkSizeBytes === 5 * 1024 * 1024
                    && $mimeType === 'text/plain';
            })
            ->andReturn($this->remoteFile());
        $progress = [];

        try {
            $result = $this->diagnostic($factory, $uploader)->run(
                function (string $message) use (&$progress): void {
                    $progress[] = $message;
                },
            );

            $this->assertTrue($result->created);
            $this->assertTrue($result->read);
            $this->assertTrue($result->trashed);
            $this->assertTrue($result->canTrash);
            $this->assertFalse($result->canDelete);
            $this->assertSame([
                '[1/5] Validando configuración...',
                '[2/5] Creando archivo temporal...',
                '[3/5] Probando escritura en Google Drive...',
                '[4/5] Verificando archivo remoto...',
                '[5/5] Moviendo archivo de prueba a la papelera...',
            ], $progress);
            $this->assertSame([], $this->temporaryFiles($temporaryRoot));
            Mail::assertNothingSent();
        } finally {
            $this->removeTemporaryFiles($credentialsPath, $temporaryRoot);
        }
    }

    public function test_logs_403_reason_and_removes_local_file_when_upload_is_forbidden(): void
    {
        [$credentialsPath, $temporaryRoot] = $this->configureDrive();
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('createUploadRequest')->once()->andReturn(Mockery::mock(RequestInterface::class));
        $gateway->shouldReceive('client')->once()->andReturn(Mockery::mock(Client::class));
        $gateway->shouldNotReceive('getFileMetadata');
        $gateway->shouldNotReceive('trashFile');
        $gateway->shouldNotReceive('deleteFile');
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')->once()->andThrow($this->googleException(
            403,
            'insufficientPermissions',
            'access_token=token-secret private_key=key-secret',
        ));
        Log::shouldReceive('error')
            ->once()
            ->with('management_history_drive_upload_test_failed', Mockery::on(function (array $context): bool {
                $serialized = json_encode($context, JSON_THROW_ON_ERROR);

                return $context['operation'] === 'upload'
                    && $context['status_code'] === 403
                    && $context['google_api_reasons'] === ['insufficientPermissions']
                    && ! str_contains($serialized, 'token-secret')
                    && ! str_contains($serialized, 'key-secret');
            }));

        try {
            try {
                $this->diagnostic($factory, $uploader)->run();
                $this->fail('Se esperaba un error de permisos de Google Drive.');
            } catch (ManagementHistoryReportStorageException $exception) {
                $this->assertSame('No fue posible escribir en Google Drive.', $exception->getMessage());
                $this->assertSame([], $this->temporaryFiles($temporaryRoot));
            }
        } finally {
            $this->removeTemporaryFiles($credentialsPath, $temporaryRoot);
        }
    }

    public function test_logs_404_metadata_reason_and_cleans_remote_and_local_files(): void
    {
        [$credentialsPath, $temporaryRoot] = $this->configureDrive();
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('createUploadRequest')->once()->andReturn(Mockery::mock(RequestInterface::class));
        $gateway->shouldReceive('client')->once()->andReturn(Mockery::mock(Client::class));
        $gateway->shouldReceive('getFileMetadata')
            ->once()
            ->with('test-file-id')
            ->andThrow($this->googleException(404, 'fileNotFound', 'File not found.'));
        $gateway->shouldReceive('trashFile')->once()->with('test-file-id');
        $gateway->shouldNotReceive('deleteFile');
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')->once()->andReturn($this->remoteFile());
        Log::shouldReceive('error')
            ->once()
            ->with('management_history_drive_upload_test_failed', Mockery::on(
                fn (array $context): bool => $context['operation'] === 'metadata'
                    && $context['status_code'] === 404
                    && $context['google_api_reasons'] === ['fileNotFound']
                    && is_string($context['file_reference'])
                    && $context['shared_drive_configured'] === true
                    && $context['supports_all_drives'] === true,
            ));

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);

            $this->diagnostic($factory, $uploader)->run();
        } finally {
            $this->assertSame([], $this->temporaryFiles($temporaryRoot));
            $this->removeTemporaryFiles($credentialsPath, $temporaryRoot);
        }
    }

    public function test_cleans_remote_file_when_validation_fails_after_upload(): void
    {
        [$credentialsPath, $temporaryRoot] = $this->configureDrive();
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('createUploadRequest')->once()->andReturn(Mockery::mock(RequestInterface::class));
        $gateway->shouldReceive('client')->once()->andReturn(Mockery::mock(Client::class));
        $gateway->shouldReceive('getFileMetadata')->once()->andThrow(new RuntimeException('metadata failed'));
        $gateway->shouldReceive('trashFile')->once()->with('test-file-id');
        $gateway->shouldNotReceive('deleteFile');
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')->once()->andReturn($this->remoteFile());
        Log::shouldReceive('error')->once();

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);

            $this->diagnostic($factory, $uploader)->run();
        } finally {
            $this->assertSame([], $this->temporaryFiles($temporaryRoot));
            $this->removeTemporaryFiles($credentialsPath, $temporaryRoot);
        }
    }

    public function test_logs_trash_failure_safely_and_retries_cleanup_without_permanent_delete(): void
    {
        [$credentialsPath, $temporaryRoot] = $this->configureDrive();
        $gateway = Mockery::mock(GoogleDriveReportGateway::class);
        $gateway->shouldReceive('createUploadRequest')->once()->andReturn(Mockery::mock(RequestInterface::class));
        $gateway->shouldReceive('client')->once()->andReturn(Mockery::mock(Client::class));
        $gateway->shouldReceive('getFileMetadata')->once()->andReturn($this->remoteFile());
        $gateway->shouldReceive('trashFile')
            ->twice()
            ->with('test-file-id')
            ->andThrowExceptions([
                $this->googleException(403, 'insufficientPermissions', 'access_token=first-secret'),
                $this->googleException(404, 'notFound', 'private_key=cleanup-secret'),
            ]);
        $gateway->shouldNotReceive('deleteFile');
        $factory = Mockery::mock(GoogleDriveReportGatewayFactory::class);
        $factory->shouldReceive('make')->once()->andReturn($gateway);
        $uploader = Mockery::mock(GoogleDriveResumableUploader::class);
        $uploader->shouldReceive('upload')->once()->andReturn($this->remoteFile());
        Log::shouldReceive('error')
            ->once()
            ->with('management_history_drive_upload_test_failed', Mockery::on(function (array $context): bool {
                $serialized = json_encode($context, JSON_THROW_ON_ERROR);

                return $context['operation'] === 'trash'
                    && $context['status_code'] === 403
                    && $context['google_api_reasons'] === ['insufficientPermissions']
                    && ! str_contains($serialized, 'first-secret');
            }));
        Log::shouldReceive('error')
            ->once()
            ->with('management_history_drive_upload_test_cleanup_failed', Mockery::on(function (array $context): bool {
                $serialized = json_encode($context, JSON_THROW_ON_ERROR);

                return $context['operation'] === 'trash'
                    && $context['status_code'] === 404
                    && $context['google_api_reasons'] === ['notFound']
                    && ! str_contains($serialized, 'cleanup-secret');
            }));

        try {
            $this->expectException(ManagementHistoryReportStorageException::class);

            $this->diagnostic($factory, $uploader)->run();
        } finally {
            $this->assertSame([], $this->temporaryFiles($temporaryRoot));
            $this->removeTemporaryFiles($credentialsPath, $temporaryRoot);
        }
    }

    private function diagnostic(
        GoogleDriveReportGatewayFactory $factory,
        GoogleDriveResumableUploader $uploader,
    ): ManagementHistoryDriveUploadDiagnostic {
        return new ManagementHistoryDriveUploadDiagnostic(
            new GoogleDriveReportConfiguration,
            $factory,
            $uploader,
            new GoogleDriveApiErrorContext,
        );
    }

    /** @return array{string, string} */
    private function configureDrive(): array
    {
        $credentialsPath = tempnam(sys_get_temp_dir(), 'kpdm-google-credentials-');
        $this->assertIsString($credentialsPath);
        $temporaryRoot = sys_get_temp_dir().DIRECTORY_SEPARATOR.'kpdm-drive-write-'.bin2hex(random_bytes(8));
        config([
            'reports.management_history.drive.enabled' => true,
            'reports.management_history.drive.credentials_path' => $credentialsPath,
            'reports.management_history.drive.folder_id' => 'reports-folder-id',
            'reports.management_history.drive.shared_drive_id' => 'shared-drive-id',
            'reports.management_history.drive.filename' => 'historico_gestiones.xlsx',
            'reports.management_history.drive.chunk_size_bytes' => 5 * 1024 * 1024,
            'reports.management_history.temporary_directory' => $temporaryRoot,
        ]);

        return [$credentialsPath, $temporaryRoot];
    }

    private function remoteFile(): DriveFile
    {
        return new DriveFile([
            'id' => 'test-file-id',
            'name' => 'kp_data_manager_drive_write_test.txt',
            'mimeType' => 'text/plain',
            'trashed' => false,
            'capabilities' => new DriveFileCapabilities([
                'canTrash' => true,
                'canDelete' => false,
            ]),
        ]);
    }

    private function googleException(int $code, string $reason, string $message): GoogleServiceException
    {
        return new GoogleServiceException(
            $message,
            $code,
            null,
            [['reason' => $reason, 'domain' => 'global']],
        );
    }

    /** @return list<string> */
    private function temporaryFiles(string $temporaryRoot): array
    {
        if (! is_dir($temporaryRoot)) {
            return [];
        }

        $paths = glob($temporaryRoot.DIRECTORY_SEPARATOR.'*');

        return $paths === false ? [] : array_values($paths);
    }

    private function removeTemporaryFiles(string $credentialsPath, string $temporaryRoot): void
    {
        @unlink($credentialsPath);

        foreach ($this->temporaryFiles($temporaryRoot) as $path) {
            if (is_dir($path)) {
                @rmdir($path);
            } else {
                @unlink($path);
            }
        }

        @rmdir($temporaryRoot);
    }
}
