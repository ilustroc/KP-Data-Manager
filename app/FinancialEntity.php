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
            self::Compartamos => 'Compartamos Financiera',
            self::Confianza => 'Financiera Confianza',
            self::Wandoo => 'Wandoo',
        };
    }

    public function isImplemented(): bool
    {
        return in_array($this, [self::Bbva, self::CajaArequipa], true);
    }

    public function profileVersion(): string
    {
        return match ($this) {
            self::Bbva, self::CajaArequipa => '1',
            default => throw new \LogicException("La entidad {$this->value} aún no tiene un perfil implementado."),
        };
    }
}
