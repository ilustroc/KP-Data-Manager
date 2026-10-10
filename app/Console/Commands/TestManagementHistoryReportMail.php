<?php

namespace App\Console\Commands;

use App\Mail\ManagementHistoryReportMail;
use App\Services\Reports\InvalidReportRecipients;
use App\Services\Reports\ManagementHistoryReportRecipients;
use DateTimeImmutable;
use DateTimeZone;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Mail;
use Throwable;

class TestManagementHistoryReportMail extends Command
{
    protected $signature = 'reports:gestiones-mail-test';

    protected $description = 'Envía un correo de prueba del reporte histórico de gestiones';

    public function handle(ManagementHistoryReportRecipients $recipients): int
    {
        try {
            $configuredRecipients = $recipients->configured();

            Mail::to($configuredRecipients)->send(new ManagementHistoryReportMail(
                generatedAt: new DateTimeImmutable('now', new DateTimeZone('UTC')),
            ));
        } catch (InvalidReportRecipients $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        } catch (Throwable $exception) {
            Log::error('Falló el correo de prueba del reporte histórico de gestiones.', [
                'exception_class' => $exception::class,
            ]);

            $this->error('No fue posible enviar el correo de prueba. Revisa la configuración de correo.');

            return self::FAILURE;
        }

        $this->info(sprintf(
            'Correo de prueba enviado a %d destinatario(s).',
            count($configuredRecipients),
        ));

        return self::SUCCESS;
    }
}
