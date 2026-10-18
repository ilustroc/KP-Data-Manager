<?php

namespace App;

enum RefreshMode: string
{
    case FullReplace = 'FULL_REPLACE';
    case ScopeReplace = 'SCOPE_REPLACE';
    case Upsert = 'UPSERT';

    public function label(): string
    {
        return match ($this) {
            self::FullReplace => 'Reemplazo completo',
            self::ScopeReplace => 'Reemplazo por alcance',
            self::Upsert => 'Actualización incremental',
        };
    }

    public function permissionColumn(): string
    {
        return match ($this) {
            self::FullReplace => 'allows_full_replace',
            self::ScopeReplace => 'allows_scope_replace',
            self::Upsert => 'allows_upsert',
        };
    }
}
