<?php

namespace App\Console\Commands;

use App\Services\Reports\ManagementHistoryDriveDiagnostic;
use Illuminate\Console\Attributes\Description;
use Illuminate\Console\Attributes\Signature;
use Illuminate\Console\Command;
use Throwable;

#[Signature('reports:gestiones-drive-test')]
#[Description('Valida la configuración y el acceso de solo lectura a Google Drive')]
class TestManagementHistoryReportDrive extends Command
{
    public function handle(ManagementHistoryDriveDiagnostic $diagnostic): int
    {
        try {
            $result = $diagnostic->run(
                progress: fn (string $message) => $this->line($message),
            );
        } catch (Throwable) {
            $this->error('No fue posible validar Google Drive. Revisa el log para obtener más información.');

            return self::FAILURE;
        }

        $this->newLine();
        $this->info('Google Drive configurado correctamente.');
        $this->line('Unidad compartida: '.($result->sharedDriveConfigured ? 'accesible' : 'no configurada'));
        $this->line('Carpeta destino: accesible');

        return self::SUCCESS;
    }
}
