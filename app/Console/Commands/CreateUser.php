<?php

namespace App\Console\Commands;

use App\Models\User;
use App\UserRole;
use Illuminate\Console\Attributes\Description;
use Illuminate\Console\Attributes\Signature;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Validator;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Rules\Password;

#[Signature('kpdm:user:create {--name=} {--email=} {--role=}')]
#[Description('Crea un usuario de KP Data Manager sin exponer la contraseña en argumentos.')]
class CreateUser extends Command
{
    /**
     * Execute the console command.
     */
    public function handle(): int
    {
        $name = trim((string) ($this->option('name') ?: $this->ask('Nombre completo')));
        $email = Str::lower(trim((string) ($this->option('email') ?: $this->ask('Correo electrónico'))));
        $role = (string) ($this->option('role') ?: $this->choice(
            'Rol',
            array_map(fn (UserRole $userRole): string => $userRole->value, UserRole::cases()),
            UserRole::ReadOnly->value,
        ));
        $password = (string) $this->secret('Contraseña (mínimo 12 caracteres, mayúsculas, minúsculas y números)');

        $validator = Validator::make([
            'name' => $name,
            'email' => $email,
            'role' => $role,
            'password' => $password,
        ], [
            'name' => ['required', 'string', 'max:100'],
            'email' => ['required', 'string', 'email', 'max:191', Rule::unique(User::class)],
            'role' => ['required', Rule::enum(UserRole::class)],
            'password' => ['required', Password::min(12)->mixedCase()->numbers()],
        ]);

        if ($validator->fails()) {
            foreach ($validator->errors()->all() as $error) {
                $this->error($error);
            }

            return self::FAILURE;
        }

        $user = User::create([
            'name' => $name,
            'email' => $email,
            'role' => UserRole::from($role),
            'password' => $password,
            'is_active' => true,
        ]);

        $this->info("Usuario {$user->email} creado con rol {$user->role->value}.");

        return self::SUCCESS;
    }
}
