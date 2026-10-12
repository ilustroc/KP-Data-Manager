<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\GoogleDriveReportGateway;
use Google\Client;
use Google\Service\Drive;
use Google\Service\Drive\Drive as SharedDrive;
use Google\Service\Drive\DriveFile;
use Google\Service\Drive\FileList;
use Google\Service\Drive\Resource\Drives;
use Google\Service\Drive\Resource\Files;
use GuzzleHttp\Psr7\Request;
use Mockery;
use Tests\TestCase;

class GoogleDriveReportGatewayTest extends TestCase
{
    public function test_authentication_uses_service_account_assertion(): void
    {
        $client = Mockery::mock(Client::class);
        $client->shouldReceive('fetchAccessTokenWithAssertion')
            ->once()
            ->andReturn(['access_token' => 'sensitive-token']);
        $drive = Mockery::mock(Drive::class);

        (new GoogleDriveReportGateway($client, $drive))->authenticateServiceAccount();

        $this->addToAssertionCount(1);
    }

    public function test_reads_shared_drive_and_folder_without_write_operations(): void
    {
        $client = Mockery::mock(Client::class);
        $drive = Mockery::mock(Drive::class);
        $drives = Mockery::mock(Drives::class);
        $files = Mockery::mock(Files::class);
        $drive->drives = $drives;
        $drive->files = $files;
        $sharedDrive = new SharedDrive(['id' => 'shared-drive-id']);
        $folder = new DriveFile([
            'id' => 'folder-id',
            'mimeType' => 'application/vnd.google-apps.folder',
            'trashed' => false,
            'driveId' => 'shared-drive-id',
        ]);
        $drives->shouldReceive('get')
            ->once()
            ->with('shared-drive-id', ['fields' => 'id,name'])
            ->andReturn($sharedDrive);
        $files->shouldReceive('get')
            ->once()
            ->with('folder-id', [
                'fields' => 'id,name,mimeType,trashed,driveId',
                'supportsAllDrives' => true,
            ])
            ->andReturn($folder);
        $files->shouldReceive('create')->never();
        $files->shouldReceive('update')->never();
        $files->shouldReceive('delete')->never();
        $gateway = new GoogleDriveReportGateway($client, $drive);

        $actualSharedDrive = $gateway->getSharedDrive('shared-drive-id');
        $actualFolder = $gateway->getFolder('folder-id');

        $this->assertSame($sharedDrive, $actualSharedDrive);
        $this->assertSame($folder, $actualFolder);
    }

    public function test_reads_capabilities_and_moves_test_file_to_trash_with_shared_drive_support(): void
    {
        $client = Mockery::mock(Client::class);
        $drive = Mockery::mock(Drive::class);
        $files = Mockery::mock(Files::class);
        $drive->files = $files;
        $metadata = new DriveFile([
            'id' => 'test-file-id',
            'name' => 'kp_data_manager_drive_write_test.txt',
        ]);
        $files->shouldReceive('get')
            ->once()
            ->with('test-file-id', [
                'fields' => 'id,name,size,webViewLink,mimeType,trashed,driveId,capabilities(canTrash,canDelete)',
                'supportsAllDrives' => true,
            ])
            ->andReturn($metadata);
        $files->shouldReceive('update')
            ->once()
            ->with(
                'test-file-id',
                Mockery::on(fn (DriveFile $file): bool => $file->getTrashed() === true),
                [
                    'fields' => 'id,trashed',
                    'supportsAllDrives' => true,
                ],
            );
        $files->shouldReceive('delete')->never();
        $gateway = new GoogleDriveReportGateway($client, $drive);

        $actualMetadata = $gateway->getFileMetadata('test-file-id');
        $gateway->trashFile('test-file-id');

        $this->assertSame($metadata, $actualMetadata);
    }

    public function test_search_is_scoped_to_folder_and_shared_drive(): void
    {
        $client = Mockery::mock(Client::class);
        $drive = Mockery::mock(Drive::class);
        $files = Mockery::mock(Files::class);
        $drive->files = $files;
        $result = new FileList;
        $result->setFiles([new DriveFile(['id' => 'matching-file-id'])]);
        $files->shouldReceive('listFiles')
            ->once()
            ->with(Mockery::on(function (array $parameters): bool {
                return $parameters['q'] === "name = 'historico_gestiones.xlsx' and 'folder-id' in parents and trashed = false"
                    && $parameters['pageSize'] === 3
                    && $parameters['supportsAllDrives'] === true
                    && $parameters['includeItemsFromAllDrives'] === true
                    && $parameters['corpora'] === 'drive'
                    && $parameters['driveId'] === 'shared-drive-id';
            }))
            ->andReturn($result);

        $matches = (new GoogleDriveReportGateway($client, $drive))->findFiles(
            'folder-id',
            'historico_gestiones.xlsx',
            'shared-drive-id',
        );

        $this->assertCount(1, $matches);
        $this->assertSame('matching-file-id', $matches[0]->getId());
    }

    public function test_create_request_uses_parent_and_supports_all_drives_without_permissions(): void
    {
        $client = Mockery::mock(Client::class);
        $client->shouldReceive('setDefer')->once()->with(true)->ordered();
        $client->shouldReceive('setDefer')->once()->with(false)->ordered();
        $drive = Mockery::mock(Drive::class);
        $files = Mockery::mock(Files::class);
        $drive->files = $files;
        $request = new Request('POST', 'https://www.googleapis.com/drive/v3/files');
        $files->shouldReceive('create')
            ->once()
            ->with(
                Mockery::on(fn (DriveFile $file): bool => $file->getName() === 'historico_gestiones.xlsx'
                    && $file->getParents() === ['folder-id']),
                Mockery::on(fn (array $parameters): bool => $parameters['supportsAllDrives'] === true
                    && str_contains($parameters['fields'], 'webViewLink')),
            )
            ->andReturn($request);

        $result = (new GoogleDriveReportGateway($client, $drive))->createUploadRequest(
            'folder-id',
            'historico_gestiones.xlsx',
        );

        $this->assertSame($request, $result);
    }

    public function test_update_request_preserves_file_id_and_supports_all_drives(): void
    {
        $client = Mockery::mock(Client::class);
        $client->shouldReceive('setDefer')->once()->with(true)->ordered();
        $client->shouldReceive('setDefer')->once()->with(false)->ordered();
        $drive = Mockery::mock(Drive::class);
        $files = Mockery::mock(Files::class);
        $drive->files = $files;
        $request = new Request('PATCH', 'https://www.googleapis.com/drive/v3/files/existing-file-id');
        $files->shouldReceive('update')
            ->once()
            ->with(
                'existing-file-id',
                Mockery::on(fn (DriveFile $file): bool => $file->getName() === 'historico_gestiones.xlsx'),
                Mockery::on(fn (array $parameters): bool => $parameters['supportsAllDrives'] === true),
            )
            ->andReturn($request);

        $result = (new GoogleDriveReportGateway($client, $drive))->updateUploadRequest(
            'existing-file-id',
            'historico_gestiones.xlsx',
        );

        $this->assertSame($request, $result);
    }
}
