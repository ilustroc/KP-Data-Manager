<?php

namespace App\Services\Reports;

use Google\Client;
use Google\Http\MediaFileUpload;
use Google\Service\Drive\DriveFile;
use Psr\Http\Message\RequestInterface;
use RuntimeException;

class GoogleDriveResumableUploader
{
    private const MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

    public function upload(
        Client $client,
        RequestInterface $request,
        string $path,
        int $sizeBytes,
        int $chunkSizeBytes,
        string $mimeType = self::MIME_TYPE,
    ): DriveFile {
        $upload = new MediaFileUpload(
            $client,
            $request,
            $mimeType,
            '',
            true,
            $chunkSizeBytes,
        );
        $upload->setFileSize($sizeBytes);

        $stream = fopen($path, 'rb');

        if ($stream === false) {
            throw new RuntimeException('No fue posible abrir el reporte temporal para subirlo.');
        }

        try {
            $result = false;

            while ($result === false && ! feof($stream)) {
                $chunk = fread($stream, $chunkSizeBytes);

                if ($chunk === false) {
                    throw new RuntimeException('No fue posible leer el reporte temporal para subirlo.');
                }

                if ($chunk === '') {
                    break;
                }

                $result = $upload->nextChunk($chunk);
            }
        } finally {
            fclose($stream);
        }

        if (! $result instanceof DriveFile) {
            throw new RuntimeException('Google Drive no confirmó la carga completa del reporte.');
        }

        return $result;
    }
}
