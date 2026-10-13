<?php

namespace App;

enum FinancialEntity: string
{
    case Bbva = 'BBVA';
    case CajaArequipa = 'CAJA_AREQUIPA';
    case Compartamos = 'COMPARTAMOS';
    case Confianza = 'CONFIANZA';
    case Wandoo = 'WANDOO';

    public function label(): string
    {
        return match ($this) {
            self::Bbva => 'BBVA',
            self::CajaArequipa => 'Caja Arequipa',
            self::Compartamos => 'Compartamos',
            self::Confianza => 'Financiera Confianza',
            self::Wandoo => 'Wandoo',
        };
    }

    public function isImplemented(): bool
    {
        return in_array($this, [self::Bbva, self::CajaArequipa, self::Compartamos, self::Confianza, self::Wandoo], true);
    }

    public function profileVersion(): string
    {
        return match ($this) {
            self::Bbva, self::CajaArequipa, self::Compartamos, self::Confianza, self::Wandoo => '1',
        };
    }
}
