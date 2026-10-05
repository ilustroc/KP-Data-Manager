<?php

namespace Tests\Feature\Payments;

use App\Models\User;
use Illuminate\Contracts\Pagination\Paginator;

class PaymentCorrectionControllerTest extends PaymentFeatureTestCase
{
    public function test_corrections_requires_authentication(): void
    {
        $this->get(route('payments.corrections'))->assertRedirectToRoute('login');
    }

    public function test_read_only_user_can_view_corrections(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null, 'OPERACION' => '0093273']);
        $this->createResolution($rawId, [
            'documento_nuevo' => '3241',
            'motivo' => 'Identificación inicial',
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.corrections'));

        $response
            ->assertViewIs('payments.corrections')
            ->assertSeeText('Identificación inicial')
            ->assertSeeText('3241')
            ->assertSeeText('0093273');
    }

    public function test_corrections_are_ordered_by_change_date_descending(): void
    {
        $olderPaymentId = $this->createPayment(['DOCUMENTO' => null]);
        $newerPaymentId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($olderPaymentId, [
            'motivo' => 'OLDER-CORRECTION',
            'fecha_modificacion' => '2026-12-18 10:30:00',
        ]);
        $this->createResolution($newerPaymentId, [
            'motivo' => 'NEWER-CORRECTION',
            'fecha_modificacion' => '2026-12-20 14:20:00',
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.corrections'));

        $response->assertSeeTextInOrder(['NEWER-CORRECTION', 'OLDER-CORRECTION']);
    }

    public function test_corrections_filters_execute_in_sql(): void
    {
        $matchingPaymentId = $this->createPayment([
            'FECHA' => '2026-12-10',
            'DOCUMENTO' => null,
            'OPERACION' => 'MATCHING-OPERATION',
        ]);
        $otherPaymentId = $this->createPayment([
            'DOCUMENTO' => null,
            'OPERACION' => 'OTHER-OPERATION',
        ]);
        $this->createResolution($matchingPaymentId, [
            'documento_anterior' => '1000',
            'documento_nuevo' => '2000',
            'usuario' => 'user:77',
            'motivo' => 'MATCHING-CORRECTION',
            'fecha_modificacion' => '2026-12-20 14:20:00',
        ]);
        $this->createResolution($otherPaymentId, [
            'documento_nuevo' => '9999',
            'usuario' => 'user:88',
            'motivo' => 'OTHER-CORRECTION',
            'fecha_modificacion' => '2026-12-01 09:00:00',
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.corrections', [
            'fecha_cambio_desde' => '2026-12-15',
            'fecha_cambio_hasta' => '2026-12-31',
            'documento' => '2000',
            'usuario' => 'user:77',
            'raw_pago_id' => $matchingPaymentId,
        ]));

        $response
            ->assertSeeText('MATCHING-CORRECTION')
            ->assertDontSeeText('OTHER-CORRECTION');
    }

    public function test_change_date_filter_uses_america_lima_day_boundaries(): void
    {
        $localDayPaymentId = $this->createPayment(['DOCUMENTO' => null]);
        $nextLocalDayPaymentId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($localDayPaymentId, [
            'motivo' => 'LOCAL-DAY-CORRECTION',
            'fecha_modificacion' => '2026-12-21 04:30:00',
        ]);
        $this->createResolution($nextLocalDayPaymentId, [
            'motivo' => 'NEXT-LOCAL-DAY-CORRECTION',
            'fecha_modificacion' => '2026-12-21 05:30:00',
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.corrections', [
            'fecha_cambio_desde' => '2026-12-20',
            'fecha_cambio_hasta' => '2026-12-20',
        ]));

        $response
            ->assertSeeText('LOCAL-DAY-CORRECTION')
            ->assertDontSeeText('NEXT-LOCAL-DAY-CORRECTION');
    }

    public function test_corrections_use_server_side_pagination(): void
    {
        for ($index = 1; $index <= 26; $index++) {
            $rawId = $this->createPayment(['DOCUMENTO' => null]);
            $this->createResolution($rawId, [
                'documento_nuevo' => 'DOC-'.$index,
                'motivo' => 'CHANGE-'.$index,
                'fecha_modificacion' => '2026-12-20 14:20:00',
            ]);
        }
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.corrections', ['per_page' => 25]));

        $response->assertViewHas(
            'corrections',
            fn (Paginator $corrections): bool => $corrections->perPage() === 25
                && count($corrections->items()) === 25
                && $corrections->nextPageUrl() !== null,
        );
    }

    public function test_empty_corrections_page_renders_empty_state(): void
    {
        $user = User::factory()->readOnly()->create();

        $this->actingAs($user)
            ->get(route('payments.corrections'))
            ->assertSeeText('No se encontraron correcciones con los filtros seleccionados.');
    }
}
