<?php

namespace Tests\Feature;

use App\Models\User;
use App\UserRole;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class DashboardTest extends TestCase
{
    use LazilyRefreshDatabase;

    public function test_guest_is_redirected_to_login(): void
    {
        $this->get(route('dashboard'))->assertRedirectToRoute('login');
    }

    #[DataProvider('activeRoles')]
    public function test_active_role_can_view_administrative_layout(UserRole $role): void
    {
        $user = User::factory()->create(['role' => $role]);

        $response = $this->actingAs($user)->get(route('dashboard'));

        $response
            ->assertViewIs('dashboard.index')
            ->assertSee('KP Data Manager')
            ->assertSee($role->label());
    }

    public function test_dashboard_escapes_user_name(): void
    {
        $dangerousName = "Jesús <script>alert('xss')</script>";
        $user = User::factory()->create(['name' => $dangerousName]);

        $response = $this->actingAs($user)->get(route('dashboard'));

        $response
            ->assertSee($dangerousName)
            ->assertDontSee($dangerousName, false);
    }

    /**
     * @return array<string, array{UserRole}>
     */
    public static function activeRoles(): array
    {
        return [
            'administrador' => [UserRole::Admin],
            'operador' => [UserRole::Operator],
            'lectura' => [UserRole::ReadOnly],
        ];
    }
}
