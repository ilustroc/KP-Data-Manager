<?php

namespace App\Services\Imports;

readonly class ImportFileMetadata
{
    public function __construct(
        public string $originalName,
        public string $extension,
        public string $mimeType,
        public int $size,
        public string $sha256,
    ) {}
}
