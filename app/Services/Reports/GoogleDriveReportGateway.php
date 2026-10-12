<?php

namespace App\Services\Reports;

use Closure;
use Google\Client;
use Google\Service\Drive;
use Google\Service\Drive\Drive as SharedDrive;
use Google\Service\Drive\DriveFile;
use LogicException;
use Psr\Http\Message\RequestInterface;

class GoogleDriveReportGateway
{
    public function __construct(
        private readonly Client $client,
        private readonly Drive $drive,
    ) {}

    /**
     * @return list<DriveFile>
     */
    public function findFiles(string $folderId, string $filename, ?string $sharedDriveId): array
    {
        $parameters = [
            'q' => sprintf(
                "name = '%s' and '%s' in parents and trashed = false",
                $this->escapeQueryValue($filename),
                $this->escapeQueryValue($folderId),
            ),
            'fields' => 'files(id,name,size,webViewLink)',
            'spaces' => 'drive',
            'pageSize' => 3,
            'supportsAllDrives' => true,
            'includeItemsFromAllDrives' => true,
        ];

        if ($sharedDriveId !== null) {
            $parameters['corpora'] = 'drive';
            $parameters['driveId'] = $sharedDriveId;
        }

        return array_values($this->drive->files->listFiles($parameters)->getFiles() ?? []);
    }

    public function createUploadRequest(string $folderId, string $filename): RequestInterface
    {
        return $this->deferredRequest(fn (): mixed => $this->drive->files->create(
            new DriveFile([
                'name' => $filename,
                'parents' => [$folderId],
            ]),
            [
                'fields' => 'id,name,size,webViewLink',
                'supportsAllDrives' => true,
            ],
        ));
    }

    public function updateUploadRequest(string $fileId, string $filename): RequestInterface
    {
        return $this->deferredRequest(fn (): mixed => $this->drive->files->update(
            $fileId,
            new DriveFile(['name' => $filename]),
            [
                'fields' => 'id,name,size,webViewLink',
                'supportsAllDrives' => true,
            ],
        ));
    }

    public function client(): Client
    {
        return $this->client;
    }

    public function authenticateServiceAccount(): void
    {
        $credentials = $this->client->fetchAccessTokenWithAssertion();

        if (! isset($credentials['access_token']) || ! is_string($credentials['access_token'])) {
            throw new LogicException('Google Drive rechazó la autenticación del Service Account.');
        }
    }

    public function getSharedDrive(string $sharedDriveId): SharedDrive
    {
        return $this->drive->drives->get($sharedDriveId, [
            'fields' => 'id,name',
        ]);
    }

    public function getFolder(string $folderId): DriveFile
    {
        return $this->drive->files->get($folderId, [
            'fields' => 'id,name,mimeType,trashed,driveId',
            'supportsAllDrives' => true,
        ]);
    }

    public function getFileMetadata(string $fileId): DriveFile
    {
        return $this->drive->files->get($fileId, [
            'fields' => 'id,name,size,webViewLink,mimeType,trashed,driveId,capabilities(canTrash,canDelete)',
            'supportsAllDrives' => true,
        ]);
    }

    public function trashFile(string $fileId): void
    {
        $this->drive->files->update(
            $fileId,
            new DriveFile(['trashed' => true]),
            [
                'fields' => 'id,trashed',
                'supportsAllDrives' => true,
            ],
        );
    }

    public function deleteFile(string $fileId): void
    {
        $this->drive->files->delete($fileId, [
            'supportsAllDrives' => true,
        ]);
    }

    private function deferredRequest(Closure $request): RequestInterface
    {
        $this->client->setDefer(true);

        try {
            $result = $request();
        } finally {
            $this->client->setDefer(false);
        }

        if (! $result instanceof RequestInterface) {
            throw new LogicException('Google Drive no devolvió una solicitud de carga válida.');
        }

        return $result;
    }

    private function escapeQueryValue(string $value): string
    {
        return str_replace(['\\', "'"], ['\\\\', "\\'"], $value);
    }
}
