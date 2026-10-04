<?php

namespace Tests\Feature\Console;

use App\Models\User;
use App\UserRole;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Tests\TestCase;

class CreateUserCommandTest extends TestCase
{
    use LazilyRefreshDatabase;

    public function test_valid_input_creates_active_user_with_hashed_password(): void
    {
        $this->artisan('kpdm:user:create', [
            '--name' => 'Administradora KP',
            '--email' => 'ADMIN@EXAMPLE.TEST',
            '--role' => UserRole::Admin->value,
        ])
            ->expectsQuestion('Contraseña (mínimo 12 caracteres, mayúsculas, minúsculas y números)', 'ClaveSegura123')
            ->expectsOutput('Usuario admin@example.test creado con rol ADMIN.')
            ->assertSuccessful();

        $user = User::query()->where('email', 'admin@example.test')->firstOrFail();

        $this->assertSame(UserRole::Admin, $user->role);
        $this->assertTrue($user->is_active);
        $this->assertTrue(Hash::check('ClaveSegura123', $user->password));
    }

    public function test_weak_password_does_not_create_user(): void
    {
        $this->artisan('kpdm:user:create', [
            '--name' => 'Operador KP',
            '--email' => 'operator@example.test',
            '--role' => UserRole::Operator->value,
        ])
            ->expectsQuestion('Contraseña (mínimo 12 caracteres, mayúsculas, minúsculas y números)', 'debil')
            ->assertFailed();

        $this->assertDatabaseMissing('users', ['email' => 'operator@example.test']);
    }
}
