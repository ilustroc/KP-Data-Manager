<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\GoogleDriveResumableUploader;
use Google\Client;
use Google\Service\Drive\DriveFile;
use GuzzleHttp\Psr7\Request;
use GuzzleHttp\Psr7\Response;
use Mockery;
use Psr\Http\Message\RequestInterface;
use Tests\TestCase;

class GoogleDriveResumableUploaderTest extends TestCase
{
    public function test_reads_file_from_disk_in_configured_chunks(): void
    {
        $path = tempnam(sys_get_temp_dir(), 'kpdm-drive-upload-');
        $this->assertIsString($path);
        file_put_contents($path, 'ABCDEFGHIJKL');
        $request = new Request(
            'POST',
            'https://www.googleapis.com/drive/v3/files',
            ['X-Php-Expected-Class' => DriveFile::class],
            '{}',
        );
        $client = Mockery::mock(Client::class);
        $client->shouldReceive('execute')
            ->once()
            ->with(
                Mockery::on(fn (RequestInterface $uploadRequest): bool => $uploadRequest->getMethod() === 'POST'
                    && str_contains($uploadRequest->getUri()->getPath(), '/upload/drive/v3/files')
                    && str_contains($uploadRequest->getUri()->getQuery(), 'uploadType=resumable')
                    && $uploadRequest->getHeaderLine('x-upload-content-type') === 'text/plain'),
                false,
            )
            ->andReturn(new Response(200, [
                'Location' => 'https://upload.example.test/resumable-session',
            ]));
        $chunkSizes = [];
        $client->shouldReceive('execute')
            ->times(3)
            ->withArgs(function (RequestInterface $chunkRequest) use (&$chunkSizes): bool {
                $chunkSizes[] = (int) $chunkRequest->getHeaderLine('content-length');

                return $chunkRequest->getMethod() === 'PUT'
                    && (string) $chunkRequest->getUri() === 'https://upload.example.test/resumable-session';
            })
            ->andReturn(
                new Response(308, ['Range' => 'bytes=0-4']),
                new Response(308, ['Range' => 'bytes=0-9']),
                new Response(200, [], json_encode([
                    'id' => 'uploaded-file-id',
                    'name' => 'historico_gestiones.xlsx',
                    'webViewLink' => 'https://drive.google.com/file/d/uploaded-file-id/view',
                ], JSON_THROW_ON_ERROR)),
            );

        try {
            $storedFile = (new GoogleDriveResumableUploader)->upload(
                client: $client,
                request: $request,
                path: $path,
                sizeBytes: 12,
                chunkSizeBytes: 5,
                mimeType: 'text/plain',
            );

            $this->assertSame([5, 5, 2], $chunkSizes);
            $this->assertSame('uploaded-file-id', $storedFile->getId());
        } finally {
            @unlink($path);
        }
    }
}
