<?php

namespace App;

use InvalidArgumentException;
use Stringable;

final readonly class SearchSourceCode implements Stringable
{
    private function __construct(public string $value) {}

    public static function from(string $value): self
    {
        $normalized = strtoupper(trim($value));

        if (preg_match('/\A[A-Z0-9][A-Z0-9_-]{0,63}\z/D', $normalized) !== 1) {
            throw new InvalidArgumentException(
                'source_code debe contener entre 1 y 64 caracteres ASCII: A-Z, 0-9, guion o guion bajo.',
            );
        }

        return new self($normalized);
    }

    public function __toString(): string
    {
        return $this->value;
    }
}
