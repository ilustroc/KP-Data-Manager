<?php

namespace App\Services\Imports;

use RuntimeException;

class DuplicateImportFile extends RuntimeException
{
    public function __construct(public readonly int $batchId)
    {
        parent::__construct("Este archivo ya fue registrado en el batch #{$batchId}.");
    }
}
