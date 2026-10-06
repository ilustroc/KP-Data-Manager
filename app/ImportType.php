<?php

namespace App;

enum ImportType: string
{
    case Payments = 'PAGOS';
    case Portfolio = 'CARTERA';

    public function label(): string
    {
        return match ($this) {
            self::Payments => 'Pagos',
            self::Portfolio => 'Cartera',
        };
    }
}
