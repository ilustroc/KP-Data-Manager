<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\ManagementHistoryReportPhone;
use App\Services\Reports\ManagementHistoryReportTransformer;
use PHPUnit\Framework\Attributes\DataProvider;
use stdClass;
use Tests\TestCase;

class ManagementHistoryReportTransformerTest extends TestCase
{
    public function test_maps_source_fields_and_converts_utc_date_to_lima(): void
    {
        $row = $this->transformer()->transform($this->sourceRow());

        $this->assertNotNull($row);
        $this->assertSame('2026-10-02 10:28:00', $row['fecha_hora']->format('Y-m-d H:i:s'));
        $this->assertSame('00001234', $row['documento']);
        $this->assertSame('934043966', $row['telefono']);
        $this->assertSame(45, $row['duracion']);
        $this->assertSame('Si', $row['promesa']);
        $this->assertSame(150.75, $row['monto']);
        $this->assertSame(1, $row['peso']);
    }

    public function test_excludes_row_when_nonempty_phone_is_invalid(): void
    {
        $source = $this->sourceRow();
        $source->telefono = '016733123';

        $this->assertNull($this->transformer()->transform($source));
    }

    public function test_includes_row_when_phone_is_empty(): void
    {
        $source = $this->sourceRow();
        $source->telefono = null;

        $row = $this->transformer()->transform($source);

        $this->assertNotNull($row);
        $this->assertNull($row['telefono']);
    }

    #[DataProvider('weights')]
    public function test_maps_every_defined_weight_exactly(string $tipificacion, int $expected): void
    {
        $this->assertSame($expected, $this->transformer()->weightFor($tipificacion));
    }

    public function test_returns_null_weight_for_unknown_or_approximate_value(): void
    {
        $transformer = $this->transformer();

        $this->assertNull($transformer->weightFor('NO_CONTESTA_EXTRA'));
        $this->assertNull($transformer->weightFor('no_contesta'));
        $this->assertNull($transformer->weightFor(null));
    }

    /** @return array<string, array{string, int}> */
    public static function weights(): array
    {
        return [
            'YA_PAGO' => ['YA_PAGO', 1],
            'ABONOS_LIBRES' => ['ABONOS_LIBRES', 2],
            'CLIENTE_PAGÓ_PARCIALMENTE_DEUDA' => ['CLIENTE_PAGÓ_PARCIALMENTE_DEUDA', 3],
            'NEGOCIACION' => ['NEGOCIACION', 4],
            'PROPUESTA_DE_PAGO' => ['PROPUESTA_DE_PAGO', 5],
            'RECORDATORIO_DE_PROMESAS' => ['RECORDATORIO_DE_PROMESAS', 6],
            'SEGUIMIENTO_CONVENIO_VIGENTE' => ['SEGUIMIENTO_CONVENIO_VIGENTE', 7],
            'CITA_TELEFONICA' => ['CITA_TELEFONICA', 8],
            'CLIENTE_INSOLVENTE' => ['CLIENTE_INSOLVENTE', 9],
            'CLIENTE_LOCALIZADO_SIN_INTERES' => ['CLIENTE_LOCALIZADO_SIN_INTERES', 10],
            'CLIENTE_RENUENTE' => ['CLIENTE_RENUENTE', 11],
            'CLIENTE_CORTA_LA_LLAMADA' => ['CLIENTE_CORTA_LA_LLAMADA', 12],
            'MENSAJE_CON_CONYUGE' => ['MENSAJE_CON_CONYUGE', 13],
            'MENSAJE_CON_FAMILIAR' => ['MENSAJE_CON_FAMILIAR', 14],
            'MENSAJE_CON_TERCERO' => ['MENSAJE_CON_TERCERO', 15],
            'FALLECIDO' => ['FALLECIDO', 16],
            'TELEFONO_EQUIVOCADO' => ['TELEFONO_EQUIVOCADO', 17],
            'FS__NO_EXISTE' => ['FS__NO_EXISTE', 18],
            'CORTAN_LLAMADA' => ['CORTAN_LLAMADA', 19],
            'CASILLA_DE_VOZ' => ['CASILLA_DE_VOZ', 20],
            'NO_CONTESTA' => ['NO_CONTESTA', 21],
        ];
    }

    private function transformer(): ManagementHistoryReportTransformer
    {
        config([
            'reports.management_history.timezone' => 'America/Lima',
            'reports.management_history.source_timezone' => 'UTC',
        ]);

        return new ManagementHistoryReportTransformer(new ManagementHistoryReportPhone);
    }

    private function sourceRow(): stdClass
    {
        return (object) [
            'created_at' => '2026-10-02 15:28:00',
            'nombre_cliente' => 'Cliente de prueba',
            'documento' => '00001234',
            'telefono' => '+51934043966',
            'agente_nombre' => 'Agente Uno',
            'canal' => 'LLAMADA',
            'tipificacion_n1' => 'CONTACTO',
            'tipificacion_n2' => 'YA_PAGO',
            'tipificacion_n3' => 'VALIDADO',
            'resultado' => 'GESTIONADO',
            'duracion' => 45,
            'promesa' => 'Si',
            'monto' => '150.75',
            'comentario' => 'Nota sintética',
        ];
    }
}
