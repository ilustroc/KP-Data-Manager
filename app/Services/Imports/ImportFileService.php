<?php

namespace App\Services\Imports;

use finfo;
use Illuminate\Contracts\Filesystem\Filesystem;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use ZipArchive;

class ImportFileService
{
    public function inspect(string $sourcePath, string $originalName, ?int $maximumBytes = null): ImportFileMetadata
    {
        if (! is_file($sourcePath) || ! is_readable($sourcePath)) {
            throw new InvalidImportFile('No se pudo leer el archivo seleccionado.');
        }

        $normalizedName = $this->normalizeOriginalName($originalName);
        $extension = strtolower((string) pathinfo($normalizedName, PATHINFO_EXTENSION));

        if (! in_array($extension, config('imports.allowed_extensions'), true)) {
            throw new InvalidImportFile('La extensión del archivo no está permitida.');
        }

        $size = filesize($sourcePath);

        if ($size === false || $size < 1) {
            throw new InvalidImportFile('El archivo está vacío o no se pudo determinar su tamaño.');
        }

        if ($maximumBytes !== null && $size > $maximumBytes) {
            throw new InvalidImportFile('El archivo excede el límite permitido para cargas web.');
        }

        $mimeType = (new finfo(FILEINFO_MIME_TYPE))->file($sourcePath);

        if ($mimeType === false || ! $this->mimeIsAllowed($extension, $mimeType)) {
            throw new InvalidImportFile('El contenido del archivo no corresponde a un formato permitido.');
        }

        if ($extension === 'xlsx') {
            $this->assertValidOpenXmlWorkbook($sourcePath);
        }

        $stream = fopen($sourcePath, 'rb');

        if ($stream === false) {
            throw new InvalidImportFile('No se pudo abrir el archivo para calcular su huella digital.');
        }

        try {
            $sha256 = $this->hashStream($stream);
        } finally {
            fclose($stream);
        }

        return new ImportFileMetadata(
            originalName: $normalizedName,
            extension: $extension,
            mimeType: $mimeType,
            size: $size,
            sha256: $sha256,
        );
    }

    /**
     * @param  resource  $stream
     */
    public function hashStream($stream): string
    {
        $context = hash_init('sha256');

        if (hash_update_stream($context, $stream) === false) {
            throw new RuntimeException('No se pudo calcular la huella digital del archivo.');
        }

        return hash_final($context);
    }

    public function storeFromPath(string $sourcePath, string $destination): void
    {
        $stream = fopen($sourcePath, 'rb');

        if ($stream === false) {
            throw new RuntimeException('No se pudo abrir el archivo para almacenarlo.');
        }

        try {
            if (! $this->disk()->put($destination, $stream)) {
                throw new RuntimeException('El almacenamiento privado rechazó el archivo.');
            }
        } finally {
            fclose($stream);
        }
    }

    public function move(string $from, string $to): void
    {
        if (! $this->disk()->move($from, $to)) {
            throw new RuntimeException('No se pudo finalizar el almacenamiento privado del archivo.');
        }
    }

    public function delete(string $path): void
    {
        if ($path !== '' && $this->disk()->exists($path)) {
            $this->disk()->delete($path);
        }
    }

    public function exists(?string $path): bool
    {
        return filled($path) && $this->disk()->exists($path);
    }

    public function disk(): Filesystem
    {
        return Storage::disk(config('imports.storage_disk'));
    }

    private function normalizeOriginalName(string $originalName): string
    {
        $name = trim((string) preg_replace('/[\x00-\x1F\x7F]/u', '', basename(str_replace('\\', '/', $originalName))));

        if ($name === '' || mb_strlen($name) > 255) {
            throw new InvalidImportFile('El nombre original del archivo no es válido.');
        }

        return $name;
    }

    private function mimeIsAllowed(string $extension, string $mimeType): bool
    {
        $allowedMimeTypes = config("imports.allowed_mime_types.{$extension}", []);

        return in_array(strtolower($mimeType), $allowedMimeTypes, true);
    }

    private function assertValidOpenXmlWorkbook(string $sourcePath): void
    {
        $archive = new ZipArchive;
        $result = $archive->open($sourcePath, ZipArchive::RDONLY);

        if ($result !== true) {
            throw new InvalidImportFile('El archivo XLSX no es un contenedor OpenXML válido.');
        }

        try {
            if ($archive->locateName('[Content_Types].xml') === false
                || $archive->locateName('xl/workbook.xml') === false) {
                throw new InvalidImportFile('El archivo XLSX no contiene una estructura de libro válida.');
            }
        } finally {
            $archive->close();
        }
    }
}
