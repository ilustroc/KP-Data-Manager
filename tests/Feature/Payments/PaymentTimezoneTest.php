<?php

namespace Tests\Feature\Payments;

use App\Models\User;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

class PaymentTimezoneTest extends PaymentFeatureTestCase
{
    public function test_new_resolution_is_persisted_in_utc(): void
    {
        $rawId = $this->createPayment([
            'DOCUMENTO' => null,
            'ingested_at' => '2026-10-05 02:24:51',
        ]);
        $user = User::factory()->operator()->create();
        $this->travelTo(Carbon::create(2026, 10, 4, 22, 33, 58, 'America/Lima'));

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Identificación con fecha UTC',
        ]);

        $this->assertDatabaseHas('pago_documento_resolucion', [
            'raw_pago_id' => $rawId,
            'fecha_modificacion' => '2026-10-05 03:33:58',
        ], 'sqlite');
    }

    public function test_visible_audit_date_uses_america_lima_and_ingestion_date_stays_hidden(): void
    {
        $rawId = $this->createPayment([
            'DOCUMENTO' => null,
            'ingested_at' => '2026-10-05 02:24:51',
        ]);
        $this->createResolution($rawId, [
            'fecha_modificacion' => '2026-10-05 03:33:58',
        ]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.show', $rawId));

        $response
            ->assertDontSeeText('04/10/2026 21:24:51')
            ->assertSeeText('04/10/2026 22:33:58')
            ->assertDontSeeText('05/10/2026 03:33:58');
    }

    public function test_ingestion_precedes_later_resolution_in_utc(): void
    {
        $rawId = $this->createPayment([
            'DOCUMENTO' => null,
            'ingested_at' => '2026-10-05 02:24:51',
        ]);
        $user = User::factory()->operator()->create();
        $this->travelTo(Carbon::create(2026, 10, 4, 22, 33, 58, 'America/Lima'));

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Identificación posterior a la ingesta',
        ]);

        $ingestedAt = DB::connection('sqlite')->table('raw_pagos')->where('raw_id', $rawId)->value('ingested_at');
        $modifiedAt = DB::connection('sqlite')->table('pago_documento_resolucion')->where('raw_pago_id', $rawId)->value('fecha_modificacion');
        $this->assertSame('2026-10-05 02:24:51', $ingestedAt);
        $this->assertSame('2026-10-05 03:33:58', $modifiedAt);
        $this->assertTrue(
            Carbon::createFromFormat('Y-m-d H:i:s', $ingestedAt, 'UTC')
                ->lessThan(Carbon::createFromFormat('Y-m-d H:i:s', $modifiedAt, 'UTC')),
        );
    }

    public function test_timezone_correction_does_not_modify_bronze(): void
    {
        $rawId = $this->createPayment([
            'DOCUMENTO' => null,
            'ingested_at' => '2026-10-05 02:24:51',
        ]);
        $bronzeBefore = (array) $this->paymentRow($rawId);
        $user = User::factory()->operator()->create();
        $this->travelTo(Carbon::create(2026, 10, 4, 22, 33, 58, 'America/Lima'));

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Identificación sin alterar Bronze',
        ]);

        $this->assertSame($bronzeBefore, (array) $this->paymentRow($rawId));
    }
}
