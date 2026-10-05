<?php

namespace Tests\Feature\Payments;

use App\Models\User;

class PaymentHistoryControllerTest extends PaymentFeatureTestCase
{
    public function test_read_only_user_can_view_complete_history(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, [
            'documento_anterior' => null,
            'documento_nuevo' => '3241',
            'activo' => 0,
        ]);
        $this->createResolution($rawId, [
            'documento_anterior' => '3241',
            'documento_nuevo' => '74900019',
            'motivo' => 'Corrección de DNI',
            'fecha_modificacion' => '2026-12-20 14:20:00',
            'activo' => 1,
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.history', $rawId));

        $response
            ->assertViewIs('payments.history')
            ->assertSeeText('3241')
            ->assertSeeText('74900019')
            ->assertSeeText('Corrección de DNI');
    }

    public function test_history_is_ordered_by_change_date_and_resolution_id_descending(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, [
            'documento_nuevo' => 'FIRST-DOCUMENT',
            'motivo' => 'FIRST-CHANGE',
            'fecha_modificacion' => '2026-12-18 10:30:00',
            'activo' => 0,
        ]);
        $this->createResolution($rawId, [
            'documento_anterior' => 'FIRST-DOCUMENT',
            'documento_nuevo' => 'SECOND-DOCUMENT',
            'motivo' => 'SECOND-CHANGE',
            'fecha_modificacion' => '2026-12-20 14:20:00',
            'activo' => 1,
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.history', $rawId));

        $response->assertSeeTextInOrder(['SECOND-CHANGE', 'FIRST-CHANGE']);
    }

    public function test_history_uses_resolution_id_as_tie_breaker(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, [
            'documento_nuevo' => 'FIRST-DOCUMENT',
            'motivo' => 'LOWER-ID',
            'fecha_modificacion' => '2026-12-20 14:20:00',
            'activo' => 0,
        ]);
        $this->createResolution($rawId, [
            'documento_anterior' => 'FIRST-DOCUMENT',
            'documento_nuevo' => 'SECOND-DOCUMENT',
            'motivo' => 'HIGHER-ID',
            'fecha_modificacion' => '2026-12-20 14:20:00',
            'activo' => 1,
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.history', $rawId));

        $response->assertSeeTextInOrder(['HIGHER-ID', 'LOWER-ID']);
    }

    public function test_history_escapes_html_in_reason(): void
    {
        $dangerousReason = "Corrección <script>alert('xss')</script>";
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, ['motivo' => $dangerousReason]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.history', $rawId));

        $response
            ->assertSee($dangerousReason)
            ->assertDontSee($dangerousReason, false);
    }

    public function test_payment_detail_contains_association_history(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => '1234']);
        $this->createResolution($rawId, [
            'documento_anterior' => '1234',
            'documento_nuevo' => '74900019',
            'motivo' => 'Corrección auditada',
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.show', $rawId));

        $response
            ->assertSeeText('Historial de asociaciones')
            ->assertSeeText('Corrección auditada')
            ->assertSeeText('1234')
            ->assertSeeText('74900019');
    }

    public function test_unauthenticated_user_cannot_view_history(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);

        $this->get(route('payments.history', $rawId))->assertRedirectToRoute('login');
    }
}
