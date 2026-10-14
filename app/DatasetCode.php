<?php

namespace App;

enum DatasetCode: string
{
    case Personas = 'PERSONAS';
    case Telefonos = 'TELEFONOS';
    case Familia = 'FAMILIA';
    case Direcciones = 'DIRECCIONES';
    case LaboralEssalud = 'LABORAL_ESSALUD';
    case Vehiculos = 'VEHICULOS';
    case Correos = 'CORREOS';
    case Sunat = 'SUNAT';
    case SbsResumen = 'SBS_RESUMEN';
    case SbsDetalle = 'SBS_DETALLE';
    case Propiedades = 'PROPIEDADES';

    public function label(): string
    {
        return match ($this) {
            self::Personas => 'Personas',
            self::Telefonos => 'Teléfonos',
            self::Familia => 'Familia',
            self::Direcciones => 'Direcciones',
            self::LaboralEssalud => 'Laboral EsSalud',
            self::Vehiculos => 'Vehículos',
            self::Correos => 'Correos',
            self::Sunat => 'SUNAT',
            self::SbsResumen => 'SBS resumen',
            self::SbsDetalle => 'SBS detalle',
            self::Propiedades => 'Propiedades',
        };
    }
}
