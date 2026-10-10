<?php

namespace App\Console\Commands;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use App\Services\Reports\InvalidReportRecipients;
use App\Services\Reports\ManagementHistoryReportService;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;
use Symfony\Component\Mailer\Exception\UnexpectedResponseException;
use Throwable;

class SendManagementHistoryReport extends Command
{
    protected $signature = 'reports:gestiones-send';

    protected $description = 'Genera y envía manualmente el reporte histórico de gestiones';

    public function handle(ManagementHistoryReportService $reports): int
    {
        try {
            $result = $reports->send(
                progress: fn (string $message) => $this->line($message),
            );
        } catch (InvalidReportRecipients $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        } catch (UnexpectedResponseException) {
            $this->error('No fue posible enviar el correo. Revisa el log para conocer la respuesta SMTP.');

            return self::FAILURE;
        } catch (ManagementHistoryReportStorageException) {
            $this->error('No fue posible almacenar el reporte en Google Drive. Revisa el log.');

            return self::FAILURE;
        } catch (Throwable $exception) {
            Log::error('Falló la generación o envío manual del reporte histórico de gestiones.', [
                'exception_class' => $exception::class,
                'exception_file' => $exception->getFile(),
                'exception_line' => $exception->getLine(),
            ]);

            $this->error('No fue posible generar o enviar el reporte histórico de gestiones.');

            return self::FAILURE;
        }

        $this->newLine();
        $this->info('Reporte histórico enviado correctamente.');
        $this->line("Periodo: {$result->period->displayStart()} - {$result->period->displayEnd()}");
        $this->line("Registros exportados: {$result->recordCount}");
        $this->line("Destinatarios: {$result->recipientCount}");
        $this->line("Archivo: {$result->filename}");

        return self::SUCCESS;
    }
}
