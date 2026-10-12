<?php

namespace App\Services\Reports;

use RuntimeException;

class InvalidReportRecipients extends RuntimeException
{
    public static function invalidConfiguration(): self
    {
        return new self('La configuración de destinatarios del reporte no es válida.');
    }

    public static function invalidAddress(): self
    {
        return new self('La configuración de destinatarios contiene una dirección de correo inválida.');
    }

    public static function noneConfigured(): self
    {
        return new self('No hay destinatarios válidos configurados para el reporte de gestiones.');
    }
}
