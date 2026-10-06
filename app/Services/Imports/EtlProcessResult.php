<?php

namespace App\Services\Imports;

final readonly class EtlProcessResult
{
    public function __construct(
        public int $exitCode,
        public float $durationSeconds,
        public ?string $lastEvent,
    ) {}

    public function successful(): bool
    {
        return $this->exitCode === 0;
    }
}
