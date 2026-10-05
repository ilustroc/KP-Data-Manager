<?php

namespace Tests\Feature\Payments;

use App\Models\User;
use App\UserRole;
use Illuminate\Support\Facades\DB;
use PHPUnit\Framework\Attributes\DataProvider;

class PaymentDocumentControllerTest extends PaymentFeatureTestCase
{
    #[DataProvider('operatorRoles')]
    public function test_operator_role_identifies_unidentified_payment(UserRole $role): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->create(['role' => $role]);

        $response = $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Identificación inicial',
        ]);

        $response
            ->assertRedirectToRoute('payments.show', $rawId)
            ->assertSessionHas('status', 'El pago fue identificado correctamente.');
        $this->assertDatabaseHas('pago_documento_resolucion', [
            'raw_pago_id' => $rawId,
            'documento_anterior' => null,
            'documento_nuevo' => '3241',
            'motivo' => 'Identificación inicial',
            'usuario' => 'user:'.$user->id,
            'activo' => 1,
        ], 'sqlite');
    }

    public function test_read_only_user_receives_403_when_identifying_payment(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Intento sin permiso',
        ]);

        $response->assertForbidden();
        $this->assertDatabaseCount('pago_documento_resolucion', 0, 'sqlite');
    }

    public function test_read_only_user_receives_403_when_correcting_payment(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => '3241']);
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900019',
            'motivo' => 'Intento sin permiso',
        ]);

        $response->assertForbidden();
        $this->assertDatabaseCount('pago_documento_resolucion', 0, 'sqlite');
    }

    public function test_unauthenticated_user_cannot_identify_payment(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);

        $response = $this->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Intento anónimo',
        ]);

        $response->assertRedirectToRoute('login');
        $this->assertDatabaseCount('pago_documento_resolucion', 0, 'sqlite');
    }

    public function test_document_is_required(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('payments.identify.create', $rawId))
            ->post(route('payments.identify', $rawId), [
                'documento' => '   ',
                'motivo' => 'Identificación inicial',
            ]);

        $response->assertInvalid([
            'documento' => 'Ingresa el documento que se asociará al pago.',
        ]);
    }

    public function test_reason_is_required(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('payments.identify.create', $rawId))
            ->post(route('payments.identify', $rawId), [
                'documento' => '3241',
                'motivo' => '   ',
            ]);

        $response->assertInvalid([
            'motivo' => 'Ingresa el motivo de la identificación o corrección.',
        ]);
    }

    public function test_document_longer_than_30_characters_is_rejected(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('payments.identify.create', $rawId))
            ->post(route('payments.identify', $rawId), [
                'documento' => str_repeat('A', 31),
                'motivo' => 'Identificación inicial',
            ]);

        $response->assertInvalid([
            'documento' => 'El documento no puede exceder 30 caracteres.',
        ]);
    }

    public function test_reason_longer_than_260_characters_is_rejected(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('payments.identify.create', $rawId))
            ->post(route('payments.identify', $rawId), [
                'documento' => '3241',
                'motivo' => str_repeat('A', 261),
            ]);

        $response->assertInvalid([
            'motivo' => 'El motivo no puede exceder 260 caracteres.',
        ]);
    }

    public function test_identification_never_modifies_bronze_payment(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();
        $bronzeBefore = (array) $this->paymentRow($rawId);

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Identificación inicial',
        ]);

        $this->assertSame($bronzeBefore, (array) $this->paymentRow($rawId));
    }

    public function test_first_resolution_is_active(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Identificación inicial',
        ]);

        $this->assertDatabaseHas('pago_documento_resolucion', [
            'raw_pago_id' => $rawId,
            'documento_nuevo' => '3241',
            'activo' => 1,
        ], 'sqlite');
    }

    public function test_second_correction_deactivates_first_and_becomes_active(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $firstResolutionId = $this->createResolution($rawId, ['documento_nuevo' => '3241']);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900019',
            'motivo' => 'Corrección de DNI',
        ]);

        $this->assertDatabaseHas('pago_documento_resolucion', [
            'id_resolucion' => $firstResolutionId,
            'activo' => 0,
        ], 'sqlite');
        $this->assertDatabaseHas('pago_documento_resolucion', [
            'raw_pago_id' => $rawId,
            'documento_nuevo' => '74900019',
            'activo' => 1,
        ], 'sqlite');
    }

    public function test_second_correction_preserves_both_history_rows(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, ['documento_nuevo' => '3241']);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900019',
            'motivo' => 'Corrección de DNI',
        ]);

        $this->assertDatabaseCount('pago_documento_resolucion', 2, 'sqlite');
    }

    public function test_correction_records_previous_effective_unhomologated_document(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, ['documento_nuevo' => '3241']);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900019',
            'motivo' => 'Corrección de DNI',
        ]);

        $this->assertDatabaseHas('pago_documento_resolucion', [
            'raw_pago_id' => $rawId,
            'documento_anterior' => '3241',
            'documento_nuevo' => '74900019',
        ], 'sqlite');
    }

    public function test_first_correction_records_original_bronze_document_as_previous_value(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => '3241']);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900019',
            'motivo' => 'Corrección desde documento original',
        ]);

        $this->assertDatabaseHas('pago_documento_resolucion', [
            'raw_pago_id' => $rawId,
            'documento_anterior' => '3241',
            'documento_nuevo' => '74900019',
        ], 'sqlite');
        $this->assertSame('3241', $this->paymentRow($rawId)->DOCUMENTO);
    }

    public function test_effective_document_changes_after_correction(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, ['documento_nuevo' => '3241']);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900019',
            'motivo' => 'Corrección de DNI',
        ]);

        $effectiveDocument = DB::connection('sqlite')
            ->table('v_pagos_actuales')
            ->where('raw_id', $rawId)
            ->value('DOCUMENTO');
        $this->assertSame('74900019', $effectiveDocument);
    }

    public function test_identified_payment_disappears_from_unidentified_view(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Identificación inicial',
        ]);

        $exists = DB::connection('sqlite')->table('v_pagos_sin_identificar')->where('raw_id', $rawId)->exists();
        $this->assertFalse($exists);
    }

    public function test_corrected_payment_is_listed_with_new_document(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, ['documento_nuevo' => '3241']);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900019',
            'motivo' => 'Corrección de DNI',
        ]);

        $this->actingAs($user)
            ->get(route('payments.index', ['documento' => '74900019']))
            ->assertSeeText('74900019');
    }

    public function test_unknown_payment_returns_404_when_identifying(): void
    {
        $user = User::factory()->operator()->create();

        $response = $this->actingAs($user)->post(route('payments.identify', 999999), [
            'documento' => '3241',
            'motivo' => 'Identificación inicial',
        ]);

        $response->assertNotFound();
    }

    public function test_identical_unhomologated_document_is_rejected(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => '3241']);
        $user = User::factory()->operator()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('payments.edit-document', $rawId))
            ->patch(route('payments.update-document', $rawId), [
                'documento' => ' 3241 ',
                'motivo' => 'Intento sin cambio real',
            ]);

        $response->assertInvalid([
            'documento' => 'El nuevo documento debe ser diferente del documento vigente.',
        ]);
        $this->assertDatabaseCount('pago_documento_resolucion', 0, 'sqlite');
    }

    public function test_competing_corrections_preserve_single_active_resolution_invariant(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $this->createResolution($rawId, ['documento_nuevo' => '3241']);
        $firstOperator = User::factory()->operator()->create();
        $secondOperator = User::factory()->operator()->create();

        $this->actingAs($firstOperator)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900018',
            'motivo' => 'Primera corrección competidora',
        ]);
        $this->actingAs($secondOperator)->patch(route('payments.update-document', $rawId), [
            'documento' => '74900019',
            'motivo' => 'Segunda corrección competidora',
        ]);

        $activeResolutions = DB::connection('sqlite')
            ->table('pago_documento_resolucion')
            ->where('raw_pago_id', $rawId)
            ->where('activo', 1)
            ->get();
        $this->assertCount(1, $activeResolutions);
        $this->assertSame('74900019', $activeResolutions->first()->documento_nuevo);
        $this->assertSame('74900018', $activeResolutions->first()->documento_anterior);
    }

    public function test_short_document_is_stored_exactly_as_entered(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => ' 3241 ',
            'motivo' => 'Identificación inicial',
        ]);

        $this->assertDatabaseHas('pago_documento_resolucion', [
            'raw_pago_id' => $rawId,
            'documento_nuevo' => '3241',
        ], 'sqlite');
    }

    public function test_alphanumeric_document_is_preserved_as_text(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => 'AB-001',
            'motivo' => 'Documento alfanumérico',
        ]);

        $this->assertDatabaseHas('pago_documento_resolucion', [
            'raw_pago_id' => $rawId,
            'documento_nuevo' => 'AB-001',
        ], 'sqlite');
    }

    public function test_silver_homologates_short_document_without_changing_audit_value(): void
    {
        $rawId = $this->createPayment(['DOCUMENTO' => null]);
        $user = User::factory()->operator()->create();

        $this->actingAs($user)->post(route('payments.identify', $rawId), [
            'documento' => '3241',
            'motivo' => 'Identificación inicial',
        ]);

        $auditDocument = DB::connection('sqlite')
            ->table('pago_documento_resolucion')
            ->where('raw_pago_id', $rawId)
            ->value('documento_nuevo');
        $silverDocument = DB::connection('sqlite')
            ->table('v_pagos_actuales')
            ->where('raw_id', $rawId)
            ->value('DOCUMENTO');
        $this->assertSame('3241', $auditDocument);
        $this->assertSame('00003241', $silverDocument);
    }

    /**
     * @return array<string, array{UserRole}>
     */
    public static function operatorRoles(): array
    {
        return [
            'administrador' => [UserRole::Admin],
            'operador' => [UserRole::Operator],
        ];
    }
}
