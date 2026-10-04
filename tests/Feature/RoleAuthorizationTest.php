<?php

namespace Tests\Feature;

use App\Models\User;
use App\UserRole;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\Facades\Route;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class RoleAuthorizationTest extends TestCase
{
    use LazilyRefreshDatabase;

    #[DataProvider('abilityMatrix')]
    public function test_role_has_expected_ability(UserRole $role, string $ability, bool $expected): void
    {
        $user = User::factory()->create(['role' => $role]);

        $allowed = Gate::forUser($user)->allows($ability);

        $this->assertSame($expected, $allowed);
    }

    public function test_read_only_user_is_forbidden_from_operator_route(): void
    {
        Route::middleware(['web', 'auth', 'active', 'role:ADMIN,OPERADOR'])
            ->get('/_tests/operator-area', fn (): string => 'permitido');
        $user = User::factory()->readOnly()->create();

        $this->actingAs($user)->get('/_tests/operator-area')->assertForbidden();
    }

    public function test_operator_user_can_access_operator_route(): void
    {
        Route::middleware(['web', 'auth', 'active', 'role:ADMIN,OPERADOR'])
            ->get('/_tests/operator-area', fn (): string => 'permitido');
        $user = User::factory()->operator()->create();

        $this->actingAs($user)
            ->get('/_tests/operator-area')
            ->assertOk()
            ->assertSeeText('permitido');
    }

    public function test_inactive_authenticated_user_is_logged_out(): void
    {
        $user = User::factory()->inactive()->create();

        $response = $this->actingAs($user)->get(route('dashboard'));

        $response
            ->assertRedirectToRoute('login')
            ->assertSessionHasErrors('email');
        $this->assertGuest();
    }

    /**
     * @return array<string, array{UserRole, string, bool}>
     */
    public static function abilityMatrix(): array
    {
        return [
            'admin administra' => [UserRole::Admin, 'administer', true],
            'admin opera' => [UserRole::Admin, 'operate', true],
            'admin consulta' => [UserRole::Admin, 'view-data', true],
            'operador no administra' => [UserRole::Operator, 'administer', false],
            'operador opera' => [UserRole::Operator, 'operate', true],
            'operador consulta' => [UserRole::Operator, 'view-data', true],
            'lectura no administra' => [UserRole::ReadOnly, 'administer', false],
            'lectura no opera' => [UserRole::ReadOnly, 'operate', false],
            'lectura consulta' => [UserRole::ReadOnly, 'view-data', true],
        ];
    }
}
