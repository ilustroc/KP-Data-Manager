<?php

namespace App\Services\Imports;

final readonly class EtlProcessResult
{
    public function __construct(
        public int $exitCode,
        public float $durationSeconds,
        public ?string $lastEvent,
        public ?string $stage,
        public ?string $errorType,
        public ?int $errorCode,
        public ?string $dbDriver,
        public ?string $connectionPhase,
        public ?bool $retryable,
        public bool $stderrPresent,
    ) {}

    public function successful(): bool
    {
        return $this->exitCode === 0;
    }
}
