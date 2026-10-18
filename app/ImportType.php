<?php

namespace App;

enum ImportType: string
{
    case Payments = 'PAGOS';
    case Portfolio = 'CARTERA';
    case Search = 'SEARCH';

    public function label(): string
    {
        return match ($this) {
            self::Payments => 'Pagos',
            self::Portfolio => 'Cartera',
            self::Search => 'KP Search',
        };
    }
}
