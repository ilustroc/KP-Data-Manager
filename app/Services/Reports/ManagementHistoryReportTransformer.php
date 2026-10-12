<?php

namespace App\Services\Reports;

use Carbon\CarbonImmutable;
use DateTimeInterface;

class ManagementHistoryReportTransformer
{
    /** @var array<string, int> */
    private const WEIGHTS = [
        'YA_PAGO' => 1,
        'ABONOS_LIBRES' => 2,
        'CLIENTE_PAGÓ_PARCIALMENTE_DEUDA' => 3,
        'NEGOCIACION' => 4,
        'PROPUESTA_DE_PAGO' => 5,
        'RECORDATORIO_DE_PROMESAS' => 6,
        'SEGUIMIENTO_CONVENIO_VIGENTE' => 7,
        'CITA_TELEFONICA' => 8,
        'CLIENTE_INSOLVENTE' => 9,
        'CLIENTE_LOCALIZADO_SIN_INTERES' => 10,
        'CLIENTE_RENUENTE' => 11,
        'CLIENTE_CORTA_LA_LLAMADA' => 12,
        'MENSAJE_CON_CONYUGE' => 13,
        'MENSAJE_CON_FAMILIAR' => 14,
        'MENSAJE_CON_TERCERO' => 15,
        'FALLECIDO' => 16,
        'TELEFONO_EQUIVOCADO' => 17,
        'FS__NO_EXISTE' => 18,
        'CORTAN_LLAMADA' => 19,
        'CASILLA_DE_VOZ' => 20,
        'NO_CONTESTA' => 21,
    ];

    public function __construct(
        private readonly ManagementHistoryReportPhone $phones,
    ) {}

    /**
     * @return array{
     *     fecha_hora: CarbonImmutable,
     *     cliente: ?string,
     *     documento: ?string,
     *     telefono: ?string,
     *     agente: ?string,
     *     canal: ?string,
     *     tipificacion_n1: ?string,
     *     tipificacion_n2: ?string,
     *     tipificacion_n3: ?string,
     *     resultado: ?string,
     *     duracion: int,
     *     promesa: string,
     *     monto: float,
     *     notas: ?string,
     *     peso: ?int
     * }|null
     */
    public function transform(object $source): ?array
    {
        $phone = $this->phones->normalize($source->telefono ?? null);

        if ($phone === false) {
            return null;
        }

        return [
            'fecha_hora' => $this->localDateTime($source->created_at),
            'cliente' => $this->nullableString($source->nombre_cliente ?? null),
            'documento' => $this->nullableString($source->documento ?? null),
            'telefono' => $phone,
            'agente' => $this->nullableString($source->agente_nombre ?? null),
            'canal' => $this->nullableString($source->canal ?? null),
            'tipificacion_n1' => $this->nullableString($source->tipificacion_n1 ?? null),
            'tipificacion_n2' => $this->nullableString($source->tipificacion_n2 ?? null),
            'tipificacion_n3' => $this->nullableString($source->tipificacion_n3 ?? null),
            'resultado' => $this->nullableString($source->resultado ?? null),
            'duracion' => (int) ($source->duracion ?? 0),
            'promesa' => (string) ($source->promesa ?? 'No'),
            'monto' => (float) ($source->monto ?? 0),
            'notas' => $this->nullableString($source->comentario ?? null),
            'peso' => $this->weightFor($source->tipificacion_n2 ?? null),
        ];
    }

    public function weightFor(mixed $tipificacionLevelTwo): ?int
    {
        if (! is_string($tipificacionLevelTwo)) {
            return null;
        }

        return self::WEIGHTS[$tipificacionLevelTwo] ?? null;
    }

    private function localDateTime(mixed $value): CarbonImmutable
    {
        $sourceTimezone = (string) config('reports.management_history.source_timezone', 'UTC');
        $localTimezone = (string) config('reports.management_history.timezone', 'America/Lima');

        if ($value instanceof DateTimeInterface) {
            return CarbonImmutable::instance($value)->setTimezone($localTimezone);
        }

        return CarbonImmutable::parse((string) $value, $sourceTimezone)->setTimezone($localTimezone);
    }

    private function nullableString(mixed $value): ?string
    {
        if ($value === null) {
            return null;
        }

        $text = (string) $value;

        return $text === '' ? null : $text;
    }
}
