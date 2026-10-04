<?php

namespace App;

enum UserRole: string
{
    case Admin = 'ADMIN';
    case Operator = 'OPERADOR';
    case ReadOnly = 'LECTURA';

    public function label(): string
    {
        return match ($this) {
            self::Admin => 'Administrador',
            self::Operator => 'Operador',
            self::ReadOnly => 'Solo lectura',
        };
    }

    public function canOperate(): bool
    {
        return in_array($this, [self::Admin, self::Operator], true);
    }
}
