<?php

namespace App\Services\Reports;

use App\Exceptions\Services\Reports\ManagementHistoryReportStorageException;
use Closure;
use Illuminate\Support\Facades\Log;
use Throwable;

class ManagementHistoryDriveDiagnostic
{
    private const FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder';

    public function __construct(
        private readonly GoogleDriveReportConfiguration $configuration,
        private readonly GoogleDriveReportGatewayFactory $gatewayFactory,
    ) {}

    public function run(?Closure $progress = null): ManagementHistoryDriveDiagnosticResult
    {
        $stage = 'configuration';

        try {
            $progress?->__invoke('[1/4] Validando configuración...');
            $settings = $this->configuration->validatedAccess();

            $stage = 'authentication';
            $progress?->__invoke('[2/4] Autenticando con Google Drive...');
            $gateway = $this->gatewayFactory->make($settings->credentialsPath);
            $gateway->authenticateServiceAccount();

            $stage = 'shared_drive';
            $progress?->__invoke('[3/4] Verificando Unidad compartida...');

            if ($settings->sharedDriveId !== null) {
                $sharedDrive = $gateway->getSharedDrive($settings->sharedDriveId);

                if (trim((string) $sharedDrive->getId()) !== $settings->sharedDriveId) {
                    throw new ManagementHistoryReportStorageException(
                        'La Unidad compartida configurada no está disponible.',
                    );
                }
            }

            $stage = 'folder';
            $progress?->__invoke('[4/4] Verificando carpeta destino...');
            $folder = $gateway->getFolder($settings->folderId);

            if (trim((string) $folder->getId()) !== $settings->folderId
                || $folder->getMimeType() !== self::FOLDER_MIME_TYPE
                || $folder->getTrashed() === true) {
                throw new ManagementHistoryReportStorageException(
                    'La carpeta de Google Drive configurada no está disponible.',
                );
            }

            if ($settings->sharedDriveId !== null && $folder->getDriveId() !== $settings->sharedDriveId) {
                throw new ManagementHistoryReportStorageException(
                    'La carpeta configurada no pertenece a la Unidad compartida esperada.',
                );
            }

            return new ManagementHistoryDriveDiagnosticResult(
                sharedDriveConfigured: $settings->sharedDriveId !== null,
            );
        } catch (Throwable $exception) {
            Log::error('management_history_drive_diagnostic_failed', [
                'stage' => $stage,
                'exception_class' => $exception::class,
                'exception_code' => is_int($exception->getCode()) ? $exception->getCode() : null,
            ]);

            if ($exception instanceof ManagementHistoryReportStorageException) {
                throw $exception;
            }

            throw new ManagementHistoryReportStorageException(
                'No fue posible validar el acceso a Google Drive.',
                previous: $exception,
            );
        }
    }
}
