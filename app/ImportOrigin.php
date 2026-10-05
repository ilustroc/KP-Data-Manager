<?php

namespace App;

enum ImportOrigin: string
{
    case Historical = 'HISTORICO';
    case Daily = 'DIARIO';
    case Manual = 'MANUAL';

    public function label(): string
    {
        return match ($this) {
            self::Historical => 'Histórico',
            self::Daily => 'Diario',
            self::Manual => 'Manual',
        };
    }
}
