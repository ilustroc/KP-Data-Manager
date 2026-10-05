<?php

namespace App;

enum ImportStatus: string
{
    case Received = 'RECIBIDO';
    case Validating = 'VALIDANDO';
    case Pending = 'PENDIENTE';
    case Processing = 'PROCESANDO';
    case Completed = 'COMPLETADO';
    case CompletedWithErrors = 'COMPLETADO_CON_ERRORES';
    case Error = 'ERROR';
    case Cancelled = 'CANCELADO';

    public function label(): string
    {
        return match ($this) {
            self::Received => 'Recibido',
            self::Validating => 'Validando',
            self::Pending => 'Pendiente',
            self::Processing => 'Procesando',
            self::Completed => 'Completado',
            self::CompletedWithErrors => 'Completado con errores',
            self::Error => 'Error',
            self::Cancelled => 'Cancelado',
        };
    }

    public function canTransitionTo(self $next): bool
    {
        return in_array($next, match ($this) {
            self::Received => [self::Validating, self::Pending, self::Error, self::Cancelled],
            self::Validating => [self::Pending, self::Error, self::Cancelled],
            self::Pending => [self::Processing, self::Error, self::Cancelled],
            self::Processing => [self::Completed, self::CompletedWithErrors, self::Error, self::Cancelled],
            self::Completed, self::CompletedWithErrors, self::Error, self::Cancelled => [],
        }, true);
    }
}
