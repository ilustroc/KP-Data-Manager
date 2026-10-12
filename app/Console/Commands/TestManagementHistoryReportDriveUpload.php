<?php

namespace App\Console\Commands;

use App\Services\Reports\ManagementHistoryDriveUploadDiagnostic;
use Illuminate\Console\Attributes\Description;
use Illuminate\Console\Attributes\Signature;
use Illuminate\Console\Command;
use Throwable;

#[Signature('reports:gestiones-drive-upload-test')]
#[Description('Valida escritura, lectura y envío a papelera de un archivo temporal en Google Drive')]
class TestManagementHistoryReportDriveUpload extends Command
{
    public function handle(ManagementHistoryDriveUploadDiagnostic $diagnostic): int
    {
        try {
            $result = $diagnostic->run(
                progress: fn (string $message) => $this->line($message),
            );
        } catch (Throwable) {
            $this->error('No fue posible escribir en Google Drive.');
            $this->line('Revisa el log para conocer el código y motivo de Google API.');

            return self::FAILURE;
        }

        $this->newLine();
        $this->info('Escritura en Google Drive validada correctamente.');
        $this->line('Creación: '.($result->created ? 'OK' : 'ERROR'));
        $this->line('Lectura: '.($result->read ? 'OK' : 'ERROR'));
        $this->line('Papelera: '.($result->trashed ? 'OK' : 'ERROR'));
        $this->line('Capabilities: canTrash='.$this->booleanLabel($result->canTrash)
            .' · canDelete='.$this->booleanLabel($result->canDelete));

        return self::SUCCESS;
    }

    private function booleanLabel(?bool $value): string
    {
        return match ($value) {
            true => 'true',
            false => 'false',
            null => 'no informado',
        };
    }
}
