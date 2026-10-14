<?php

namespace App\Services\Imports;

use App\DatasetCode;
use App\RefreshMode;
use App\SearchSourceCode;
use InvalidArgumentException;
use JsonException;

final class SearchImportIdempotencyKey
{
    /**
     * @throws JsonException
     */
    public function make(
        DatasetCode $dataset,
        SearchSourceCode $source,
        RefreshMode $refreshMode,
        string $profileVersion,
        int $mappingVersion,
        string $fileSha256,
    ): string {
        $profileVersion = trim($profileVersion);
        $fileSha256 = strtolower(trim($fileSha256));

        if ($profileVersion === '' || strlen($profileVersion) > 20) {
            throw new InvalidArgumentException('profileVersion debe contener entre 1 y 20 caracteres.');
        }

        if ($mappingVersion < 1) {
            throw new InvalidArgumentException('mappingVersion debe ser mayor que cero.');
        }

        if (preg_match('/\A[0-9a-f]{64}\z/D', $fileSha256) !== 1) {
            throw new InvalidArgumentException('fileSha256 debe ser un SHA-256 hexadecimal válido.');
        }

        $identity = json_encode([
            'dataset' => $dataset->value,
            'source' => $source->value,
            'refresh_mode' => $refreshMode->value,
            'profile_version' => $profileVersion,
            'mapping_version' => $mappingVersion,
            'file_sha256' => $fileSha256,
        ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);

        return hash('sha256', $identity);
    }
}
