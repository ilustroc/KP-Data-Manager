<?php

declare(strict_types=1);

use App\Services\Imports\ImportFileAccessException;
use App\Services\Imports\ImportFileAccessService;
use Illuminate\Contracts\Console\Kernel;
use Illuminate\Support\Facades\Storage;

require dirname(__DIR__, 2).'/vendor/autoload.php';

$application = require dirname(__DIR__, 2).'/bootstrap/app.php';
$application->make(Kernel::class)->bootstrap();

$storageRoot = getenv('KPDM_TEST_IMPORT_ROOT');
$etlUser = getenv('KPDM_TEST_ETL_USER');
$sharedGroup = getenv('KPDM_TEST_SHARED_GROUP');
$expectedFailure = getenv('KPDM_TEST_EXPECT_FAILURE') === '1';

if (! is_string($storageRoot) || $storageRoot === ''
    || ! is_string($etlUser) || $etlUser === ''
    || ! is_string($sharedGroup) || $sharedGroup === '') {
    fwrite(STDERR, "Faltan variables de la prueba POSIX.\n");
    exit(2);
}

config([
    'filesystems.disks.imports.root' => $storageRoot,
    'imports.storage_disk' => 'imports',
    'imports.private_files.enforce_before_dispatch' => true,
    'imports.private_files.etl_user' => $etlUser,
    'imports.private_files.shared_group' => $sharedGroup,
    'imports.private_files.file_mode' => 0640,
    'imports.private_files.directory_mode' => 02750,
]);
Storage::forgetDisk('imports');

$relativePath = '2026/10/permission-check.csv';
Storage::disk('imports')->put(
    $relativePath,
    "DOCUMENTO,TELEFONO\n00003862,934043966\n",
);

try {
    $application->make(ImportFileAccessService::class)->prepare($relativePath);
} catch (ImportFileAccessException $exception) {
    if ($expectedFailure) {
        fwrite(STDOUT, $exception->getMessage()."\n");
        exit(0);
    }

    throw $exception;
}

if ($expectedFailure) {
    fwrite(STDERR, "La validación debía rechazar al usuario ETL sin acceso.\n");
    exit(3);
}

fwrite(STDOUT, Storage::disk('imports')->path($relativePath)."\n");
