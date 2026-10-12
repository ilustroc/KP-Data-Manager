<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Reporte histórico de gestiones</title>
</head>
<body style="margin: 0; background-color: #f4f6f8; color: #202124; font-family: Arial, Helvetica, sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f4f6f8; padding: 24px 12px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 620px; background-color: #ffffff; border: 1px solid #dadfe5;">
                    <tr>
                        <td style="background-color: #062b60; padding: 18px 24px; color: #ffffff; font-size: 18px; font-weight: 700;">
                            KP INVEST
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 28px 24px;">
                            <h1 style="margin: 0 0 16px; color: #062b60; font-size: 24px; line-height: 1.25;">
                                Reporte histórico de gestiones
                            </h1>
                            <p style="margin: 0 0 20px; color: #5f6b7a; font-size: 14px; line-height: 1.6;">
                                @if ($downloadUrl !== null)
                                    El reporte histórico de gestiones se encuentra disponible en Google Drive.
                                @else
                                    Se ha generado correctamente el reporte histórico de gestiones.
                                @endif
                            </p>

                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse: collapse; font-size: 14px;">
                                @if ($periodFromDisplay !== null || $periodToDisplay !== null)
                                    <tr>
                                        <td style="width: 140px; border-top: 1px solid #dadfe5; padding: 10px 0; color: #5f6b7a;">Periodo</td>
                                        <td style="border-top: 1px solid #dadfe5; padding: 10px 0; font-weight: 600;">
                                            {{ $periodFromDisplay ?? 'Sin fecha inicial' }} al {{ $periodToDisplay ?? 'Sin fecha final' }}
                                        </td>
                                    </tr>
                                @endif

                                @if ($recordCount !== null)
                                    <tr>
                                        <td style="width: 140px; border-top: 1px solid #dadfe5; padding: 10px 0; color: #5f6b7a;">Registros</td>
                                        <td style="border-top: 1px solid #dadfe5; padding: 10px 0; font-weight: 600;">{{ number_format($recordCount) }}</td>
                                    </tr>
                                @endif

                                @if ($filename !== null)
                                    <tr>
                                        <td style="width: 140px; border-top: 1px solid #dadfe5; padding: 10px 0; color: #5f6b7a;">Archivo</td>
                                        <td style="border-top: 1px solid #dadfe5; padding: 10px 0; font-weight: 600;">{{ $filename }}</td>
                                    </tr>
                                @endif

                                <tr>
                                    <td style="width: 140px; border-top: 1px solid #dadfe5; padding: 10px 0; color: #5f6b7a;">Generado</td>
                                    <td style="border-top: 1px solid #dadfe5; padding: 10px 0; font-weight: 600;">{{ $generatedAtDisplay }}</td>
                                </tr>
                            </table>

                            @if ($downloadUrl !== null)
                                <table role="presentation" cellspacing="0" cellpadding="0" style="margin: 24px 0 0;">
                                    <tr>
                                        <td style="background-color: #1769e0; border-radius: 3px;">
                                            <a href="{{ $downloadUrl }}" target="_blank" rel="noopener noreferrer" style="display: inline-block; padding: 11px 18px; color: #ffffff; font-size: 13px; font-weight: 700; text-decoration: none;">
                                                DESCARGAR REPORTE
                                            </a>
                                        </td>
                                    </tr>
                                </table>

                                <p style="margin: 16px 0 0; color: #7a8491; font-size: 12px; line-height: 1.5;">
                                    El acceso al archivo está sujeto a los permisos configurados en Google Drive.
                                </p>
                            @endif

                            <p style="margin: 24px 0 0; color: #7a8491; font-size: 12px; line-height: 1.5;">
                                Este es un correo automático. Por favor, no respondas a este mensaje.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
