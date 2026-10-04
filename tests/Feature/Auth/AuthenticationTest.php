<?php

namespace Tests\Feature\Auth;

use App\Models\User;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Tests\TestCase;

class AuthenticationTest extends TestCase
{
    use LazilyRefreshDatabase;

    public function test_guest_can_view_login_screen(): void
    {
        $this->get(route('login'))
            ->assertViewIs('auth.login')
            ->assertSee('Inicia sesión');
    }

    public function test_active_user_can_authenticate_with_valid_credentials(): void
    {
        $user = User::factory()->create(['password' => 'Secret123!']);

        $response = $this->post(route('login.store'), [
            'email' => '  '.strtoupper($user->email).'  ',
            'password' => 'Secret123!',
        ]);

        $response->assertRedirectToRoute('dashboard');
        $this->assertAuthenticatedAs($user);
    }

    public function test_invalid_credentials_are_rejected(): void
    {
        $user = User::factory()->create(['password' => 'Secret123!']);

        $response = $this->from(route('login'))->post(route('login.store'), [
            'email' => $user->email,
            'password' => 'incorrecta',
        ]);

        $response
            ->assertRedirect(route('login'))
            ->assertSessionHasErrors('email');
        $this->assertGuest();
    }

    public function test_inactive_user_cannot_authenticate(): void
    {
        $user = User::factory()->inactive()->create(['password' => 'Secret123!']);

        $response = $this->from(route('login'))->post(route('login.store'), [
            'email' => $user->email,
            'password' => 'Secret123!',
        ]);

        $response
            ->assertRedirect(route('login'))
            ->assertSessionHasErrors('email');
        $this->assertGuest();
    }

    public function test_authenticated_user_can_log_out(): void
    {
        $user = User::factory()->create();

        $response = $this->actingAs($user)->post(route('logout'));

        $response->assertRedirectToRoute('login');
        $this->assertGuest();
    }

    public function test_login_is_rate_limited_after_repeated_failures(): void
    {
        $email = 'rate-limit@example.test';

        foreach (range(1, 5) as $attempt) {
            $this->post(route('login.store'), [
                'email' => $email,
                'password' => 'incorrecta',
            ])->assertSessionHasErrors('email');
        }

        $this->post(route('login.store'), [
            'email' => $email,
            'password' => 'incorrecta',
        ])->assertTooManyRequests();
    }
}
