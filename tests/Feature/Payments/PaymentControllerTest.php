<?php

namespace Tests\Feature\Payments;

use App\Models\User;
use App\UserRole;
use Illuminate\Contracts\Pagination\Paginator;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class PaymentControllerTest extends TestCase
{
    use LazilyRefreshDatabase;

    private int $nextPaymentId = 1;

    protected function setUp(): void
    {
        parent::setUp();

        $this->withoutVite();
        config(['payments.connection' => 'sqlite']);

        $this->createPaymentViews();
    }

    public function test_unauthenticated_user_cannot_access_payments(): void
    {
        $this->get(route('payments.index'))->assertRedirectToRoute('login');
    }

    #[DataProvider('activeRoles')]
    public function test_active_role_can_access_payments(UserRole $role): void
    {
        $user = User::factory()->create(['role' => $role]);

        $response = $this->actingAs($user)->get(route('payments.index'));

        $response
            ->assertViewIs('payments.index')
            ->assertSeeText('Consulta consolidada de pagos históricos y actuales.');
    }

    public function test_inactive_user_cannot_access_payments(): void
    {
        $user = User::factory()->inactive()->create();

        $response = $this->actingAs($user)->get(route('payments.index'));

        $response
            ->assertRedirectToRoute('login')
            ->assertSessionHasErrors('email');
        $this->assertGuest();
    }

    public function test_empty_payment_list_renders_empty_state(): void
    {
        $user = User::factory()->readOnly()->create();

        $response = $this->actingAs($user)->get(route('payments.index'));

        $response
            ->assertOk()
            ->assertSeeText('No se encontraron pagos con los filtros seleccionados.');
    }

    public function test_document_filter_returns_matching_effective_document(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['DOCUMENTO' => '00074901', 'OPERACION' => 'DOC-MATCH']);
        $this->createPayment(['DOCUMENTO' => '12345678', 'OPERACION' => 'DOC-OTHER']);

        $response = $this->actingAs($user)->get(route('payments.index', ['documento' => '0007']));

        $response
            ->assertSeeText('DOC-MATCH')
            ->assertDontSeeText('DOC-OTHER');
    }

    public function test_operation_filter_returns_matching_operation(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['OPERACION' => '0060814']);
        $this->createPayment(['OPERACION' => '01400800']);

        $response = $this->actingAs($user)->get(route('payments.index', ['operacion' => '006']));

        $response
            ->assertSeeText('0060814')
            ->assertDontSeeText('01400800');
    }

    public function test_collection_filter_uses_exact_value(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['RECAUDO' => 'BCP', 'OPERACION' => 'BANK-BCP']);
        $this->createPayment(['RECAUDO' => 'BCP APP', 'OPERACION' => 'BANK-APP']);

        $response = $this->actingAs($user)->get(route('payments.index', ['recaudo' => 'BCP']));

        $response
            ->assertSeeText('BANK-BCP')
            ->assertDontSeeText('BANK-APP');
    }

    public function test_date_range_filter_returns_only_payments_inside_range(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['FECHA' => '2026-10-01', 'OPERACION' => 'DATE-IN']);
        $this->createPayment(['FECHA' => '2026-09-30', 'OPERACION' => 'DATE-BEFORE']);
        $this->createPayment(['FECHA' => '2026-10-08', 'OPERACION' => 'DATE-AFTER']);

        $response = $this->actingAs($user)->get(route('payments.index', [
            'fecha_desde' => '2026-10-01',
            'fecha_hasta' => '2026-10-07',
        ]));

        $response
            ->assertSeeText('DATE-IN')
            ->assertDontSeeText('DATE-BEFORE')
            ->assertDontSeeText('DATE-AFTER');
    }

    public function test_amount_range_filter_returns_only_payments_inside_range(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['MONTO' => '1250.50', 'OPERACION' => 'AMOUNT-IN']);
        $this->createPayment(['MONTO' => '99.99', 'OPERACION' => 'AMOUNT-BELOW']);
        $this->createPayment(['MONTO' => '2500.00', 'OPERACION' => 'AMOUNT-ABOVE']);

        $response = $this->actingAs($user)->get(route('payments.index', [
            'monto_min' => '1000',
            'monto_max' => '2000',
        ]));

        $response
            ->assertSeeText('AMOUNT-IN')
            ->assertDontSeeText('AMOUNT-BELOW')
            ->assertDontSeeText('AMOUNT-ABOVE');
    }

    public function test_identified_status_returns_only_nonblank_documents(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['DOCUMENTO' => '74900018', 'OPERACION' => 'IDENTIFIED']);
        $this->createPayment(['DOCUMENTO' => null, 'OPERACION' => 'NULL-DOCUMENT']);
        $this->createPayment(['DOCUMENTO' => '   ', 'OPERACION' => 'BLANK-DOCUMENT']);

        $response = $this->actingAs($user)->get(route('payments.index', ['estado' => 'identificados']));

        $response
            ->assertSeeText('IDENTIFIED')
            ->assertDontSeeText('NULL-DOCUMENT')
            ->assertDontSeeText('BLANK-DOCUMENT');
    }

    public function test_unidentified_status_returns_null_and_blank_documents(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['DOCUMENTO' => '74900018', 'OPERACION' => 'IDENTIFIED']);
        $this->createPayment(['DOCUMENTO' => null, 'OPERACION' => 'NULL-DOCUMENT']);
        $this->createPayment(['DOCUMENTO' => '   ', 'OPERACION' => 'BLANK-DOCUMENT']);

        $response = $this->actingAs($user)->get(route('payments.index', ['estado' => 'sin_identificar']));

        $response
            ->assertDontSeeText('IDENTIFIED')
            ->assertSeeText('NULL-DOCUMENT')
            ->assertSeeText('BLANK-DOCUMENT');
    }

    public function test_unidentified_page_uses_unidentified_view(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['DOCUMENTO' => '74900018', 'OPERACION' => 'HAS-DOCUMENT']);
        $this->createPayment(['DOCUMENTO' => null, 'OPERACION' => 'NO-DOCUMENT']);

        $response = $this->actingAs($user)->get(route('payments.unidentified'));

        $response
            ->assertViewIs('payments.unidentified')
            ->assertSeeText('NO-DOCUMENT')
            ->assertDontSeeText('HAS-DOCUMENT');
    }

    #[DataProvider('pageSizes')]
    public function test_allowed_page_size_is_applied(int $pageSize): void
    {
        $user = User::factory()->readOnly()->create();

        for ($index = 0; $index <= $pageSize; $index++) {
            $this->createPayment(['OPERACION' => 'PAGE-'.$index]);
        }

        $response = $this->actingAs($user)->get(route('payments.index', ['per_page' => $pageSize]));

        $response->assertViewHas(
            'payments',
            fn (Paginator $payments): bool => $payments->perPage() === $pageSize
                && count($payments->items()) === $pageSize
                && $payments->nextPageUrl() !== null,
        );
    }

    public function test_invalid_page_size_returns_controlled_validation_error(): void
    {
        $user = User::factory()->readOnly()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('payments.index'))
            ->get(route('payments.index', ['per_page' => 30]));

        $response
            ->assertRedirect(route('payments.index'))
            ->assertInvalid(['per_page' => 'La cantidad por página debe ser 25, 50 o 100.']);
    }

    public function test_end_date_before_start_date_returns_validation_error(): void
    {
        $user = User::factory()->readOnly()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('payments.index'))
            ->get(route('payments.index', [
                'fecha_desde' => '2026-10-10',
                'fecha_hasta' => '2026-10-01',
            ]));

        $response->assertInvalid([
            'fecha_hasta' => 'La fecha hasta debe ser igual o posterior a la fecha desde.',
        ]);
    }

    public function test_maximum_amount_below_minimum_amount_returns_validation_error(): void
    {
        $user = User::factory()->readOnly()->create();

        $response = $this
            ->actingAs($user)
            ->from(route('payments.index'))
            ->get(route('payments.index', [
                'monto_min' => '300.00',
                'monto_max' => '299.99',
            ]));

        $response->assertInvalid([
            'monto_max' => 'El monto máximo debe ser mayor o igual al monto mínimo.',
        ]);
    }

    public function test_existing_payment_detail_is_read_only_and_complete(): void
    {
        $user = User::factory()->readOnly()->create();
        $rawId = $this->createPayment([
            'FECHA' => '2026-10-01',
            'DOCUMENTO_ORIGINAL' => 'ORIGINAL-HIDDEN',
            'DOCUMENTO' => '00074918',
            'MONTO' => '1250.50',
            'ACUMULADO' => '1450.75',
            'RECAUDO' => 'BCP',
            'OPERACION' => '0060814',
            'COMENTARIO' => 'Pago confirmado por tesorería.',
            'HORA' => '21:05:36',
            'source_file' => 'pagos_octubre.csv',
            'batch_id' => 'batch-2026-10',
            'ingested_at' => '2026-10-01 22:00:00',
        ]);

        $response = $this->actingAs($user)->get(route('payments.show', $rawId));

        $response
            ->assertOk()
            ->assertSeeText('Pago #'.$rawId)
            ->assertSeeText('01/10/2026')
            ->assertSeeText('21:05:36')
            ->assertSeeText('00074918')
            ->assertSeeText('S/ 1,250.50')
            ->assertSeeText('S/ 1,450.75')
            ->assertSeeText('BCP')
            ->assertSeeText('0060814')
            ->assertSeeText('Pago confirmado por tesorería.')
            ->assertSeeText('pagos_octubre.csv')
            ->assertSeeText('batch-2026-10')
            ->assertSeeText('01/10/2026 22:00:00')
            ->assertDontSeeText('ORIGINAL-HIDDEN')
            ->assertDontSeeText('Editar')
            ->assertDontSeeText('Identificar');
    }

    public function test_unknown_payment_returns_404(): void
    {
        $user = User::factory()->readOnly()->create();

        $this->actingAs($user)->get(route('payments.show', 999999))->assertNotFound();
    }

    public function test_operation_preserves_leading_zeroes(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['OPERACION' => '0093273']);

        $this->actingAs($user)
            ->get(route('payments.index'))
            ->assertSeeText('0093273');
    }

    public function test_document_preserves_leading_zeroes(): void
    {
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['DOCUMENTO' => '00001234']);

        $this->actingAs($user)
            ->get(route('payments.index'))
            ->assertSeeText('00001234');
    }

    public function test_payment_comment_is_html_escaped(): void
    {
        $dangerousComment = "Pago <script>alert('xss')</script>";
        $user = User::factory()->readOnly()->create();
        $this->createPayment(['COMENTARIO' => $dangerousComment]);

        $response = $this->actingAs($user)->get(route('payments.index'));

        $response
            ->assertSee($dangerousComment)
            ->assertDontSee($dangerousComment, false);
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

    /**
     * @return array<string, array{int}>
     */
    public static function pageSizes(): array
    {
        return [
            '25 filas' => [25],
            '50 filas' => [50],
            '100 filas' => [100],
        ];
    }

    private function createPaymentViews(): void
    {
        DB::connection('sqlite')->statement('DROP VIEW IF EXISTS v_pagos_sin_identificar');
        DB::connection('sqlite')->statement('DROP VIEW IF EXISTS v_pagos_actuales');
        Schema::connection('sqlite')->dropIfExists('payment_source');

        Schema::connection('sqlite')->create('payment_source', function (Blueprint $table): void {
            $table->unsignedBigInteger('raw_id')->primary();
            $table->date('FECHA')->nullable();
            $table->string('DOCUMENTO_ORIGINAL', 30)->nullable();
            $table->string('DOCUMENTO', 30)->nullable();
            $table->decimal('MONTO', 15, 2)->nullable();
            $table->decimal('ACUMULADO', 15, 2)->nullable();
            $table->string('RECAUDO', 50)->nullable();
            $table->string('OPERACION', 100)->nullable();
            $table->string('COMENTARIO', 260)->nullable();
            $table->time('HORA')->nullable();
            $table->string('source_file')->nullable();
            $table->string('batch_id', 100)->nullable();
            $table->dateTime('ingested_at')->nullable();
        });

        DB::connection('sqlite')->statement(<<<'SQL'
            CREATE VIEW v_pagos_actuales AS
            SELECT raw_id, FECHA, DOCUMENTO_ORIGINAL, DOCUMENTO, MONTO, ACUMULADO,
                   RECAUDO, OPERACION, COMENTARIO, HORA, source_file, batch_id, ingested_at
            FROM payment_source
            SQL);

        DB::connection('sqlite')->statement(<<<'SQL'
            CREATE VIEW v_pagos_sin_identificar AS
            SELECT raw_id, FECHA, DOCUMENTO_ORIGINAL, DOCUMENTO, MONTO, ACUMULADO,
                   RECAUDO, OPERACION, COMENTARIO, HORA, source_file, batch_id, ingested_at
            FROM v_pagos_actuales
            WHERE DOCUMENTO IS NULL OR TRIM(DOCUMENTO) = ''
            SQL);
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    private function createPayment(array $overrides = []): int
    {
        $rawId = $overrides['raw_id'] ?? $this->nextPaymentId++;

        DB::connection('sqlite')->table('payment_source')->insert(array_merge([
            'raw_id' => $rawId,
            'FECHA' => '2026-10-01',
            'DOCUMENTO_ORIGINAL' => '74900018',
            'DOCUMENTO' => '74900018',
            'MONTO' => '300.00',
            'ACUMULADO' => '300.00',
            'RECAUDO' => 'BCP',
            'OPERACION' => '0060814',
            'COMENTARIO' => 'Pago de prueba',
            'HORA' => '21:05:36',
            'source_file' => 'payments.csv',
            'batch_id' => 'batch-test',
            'ingested_at' => '2026-10-01 22:00:00',
        ], $overrides));

        return (int) $rawId;
    }
}
