<?php

namespace App;

enum ImportType: string
{
    case Payments = 'PAGOS';

    public function label(): string
    {
        return match ($this) {
            self::Payments => 'Pagos',
        };
    }
}
