<?php

namespace Tests\Feature\Payments;

use Illuminate\Database\Schema\Blueprint;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;
use Tests\TestCase;

abstract class PaymentFeatureTestCase extends TestCase
{
    use LazilyRefreshDatabase;

    private int $nextPaymentId = 1;

    protected function setUp(): void
    {
        parent::setUp();

        $this->withoutVite();
        config([
            'payments.connection' => 'sqlite',
            'payments.control_connection' => 'sqlite',
            'payments.views.current' => 'v_pagos_actuales',
            'payments.views.unidentified' => 'v_pagos_sin_identificar',
            'payments.tables.raw' => 'raw_pagos',
            'payments.tables.resolutions' => 'pago_documento_resolucion',
            'payments.tables.audit_current' => 'v_pagos_actuales',
        ]);

        $this->createPaymentSchema();
    }

    /**
     * @param  array<string, mixed>  $overrides
     */
    protected function createPayment(array $overrides = []): int
    {
        $rawId = $overrides['raw_id'] ?? $this->nextPaymentId++;

        DB::connection('sqlite')->table('raw_pagos')->insert(array_merge([
            'raw_id' => $rawId,
            'FECHA' => '2026-10-01',
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

    /**
     * @param  array<string, mixed>  $overrides
     */
    protected function createResolution(int $rawId, array $overrides = []): int
    {
        return (int) DB::connection('sqlite')->table('pago_documento_resolucion')->insertGetId(array_merge([
            'raw_pago_id' => $rawId,
            'documento_anterior' => null,
            'documento_nuevo' => '3241',
            'motivo' => 'Identificación inicial',
            'usuario' => 'user:1',
            'fecha_modificacion' => '2026-10-01 10:00:00',
            'activo' => 1,
        ], $overrides), 'id_resolucion');
    }

    protected function paymentRow(int $rawId): object
    {
        return DB::connection('sqlite')->table('raw_pagos')->where('raw_id', $rawId)->firstOrFail();
    }

    private function createPaymentSchema(): void
    {
        DB::connection('sqlite')->statement('DROP VIEW IF EXISTS v_pagos_sin_identificar');
        DB::connection('sqlite')->statement('DROP VIEW IF EXISTS v_pagos_actuales');
        Schema::connection('sqlite')->dropIfExists('pago_documento_resolucion');
        Schema::connection('sqlite')->dropIfExists('raw_pagos');

        Schema::connection('sqlite')->create('raw_pagos', function (Blueprint $table): void {
            $table->unsignedBigInteger('raw_id')->primary();
            $table->date('FECHA')->nullable();
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

        Schema::connection('sqlite')->create('pago_documento_resolucion', function (Blueprint $table): void {
            $table->id('id_resolucion');
            $table->unsignedBigInteger('raw_pago_id');
            $table->string('documento_anterior', 30)->nullable();
            $table->string('documento_nuevo', 30);
            $table->string('motivo', 260)->nullable();
            $table->string('usuario', 100);
            $table->dateTime('fecha_modificacion');
            $table->boolean('activo')->default(true);
            $table->index(['raw_pago_id', 'activo'], 'idx_pago_resolucion_raw_activo');
        });

        DB::connection('sqlite')->statement(<<<'SQL'
            CREATE VIEW v_pagos_actuales AS
            SELECT
                p.raw_id,
                p.FECHA,
                p.DOCUMENTO AS DOCUMENTO_ORIGINAL,
                CASE
                    WHEN COALESCE(r.documento_nuevo, p.DOCUMENTO) IS NULL THEN NULL
                    WHEN TRIM(COALESCE(r.documento_nuevo, p.DOCUMENTO)) = '' THEN ''
                    WHEN TRIM(COALESCE(r.documento_nuevo, p.DOCUMENTO)) NOT GLOB '*[^0-9]*'
                         AND LENGTH(TRIM(COALESCE(r.documento_nuevo, p.DOCUMENTO))) < 8
                        THEN SUBSTR('00000000' || TRIM(COALESCE(r.documento_nuevo, p.DOCUMENTO)), -8, 8)
                    ELSE TRIM(COALESCE(r.documento_nuevo, p.DOCUMENTO))
                END AS DOCUMENTO,
                p.MONTO,
                p.ACUMULADO,
                p.RECAUDO,
                p.OPERACION,
                p.COMENTARIO,
                p.HORA,
                p.source_file,
                p.batch_id,
                p.ingested_at
            FROM raw_pagos AS p
            LEFT JOIN pago_documento_resolucion AS r
                ON r.raw_pago_id = p.raw_id AND r.activo = 1
            SQL);

        DB::connection('sqlite')->statement(<<<'SQL'
            CREATE VIEW v_pagos_sin_identificar AS
            SELECT raw_id, FECHA, DOCUMENTO_ORIGINAL, DOCUMENTO, MONTO, ACUMULADO,
                   RECAUDO, OPERACION, COMENTARIO, HORA, source_file, batch_id, ingested_at
            FROM v_pagos_actuales
            WHERE DOCUMENTO IS NULL OR TRIM(DOCUMENTO) = ''
            SQL);

    }
}
