<?php

namespace App\Services\Payments;

use App\Models\User;
use Illuminate\Database\Connection;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

class PaymentResolutionService
{
    public function identify(int $rawId, string $document, string $reason, User $user): int
    {
        return $this->resolve($rawId, $document, $reason, $user, requiresUnidentified: true);
    }

    public function correct(int $rawId, string $document, string $reason, User $user): int
    {
        return $this->resolve($rawId, $document, $reason, $user, requiresUnidentified: false);
    }

    private function resolve(
        int $rawId,
        string $document,
        string $reason,
        User $user,
        bool $requiresUnidentified,
    ): int {
        $document = trim($document);
        $reason = trim($reason);
        $connection = $this->connection();

        $this->acquirePaymentLock($connection, $rawId);

        try {
            return $connection->transaction(function () use (
                $connection,
                $rawId,
                $document,
                $reason,
                $user,
                $requiresUnidentified,
            ): int {
                $rawPayment = $connection
                    ->table(config('payments.tables.raw'))
                    ->select(['raw_id', 'DOCUMENTO'])
                    ->where('raw_id', $rawId)
                    ->first();

                if ($rawPayment === null) {
                    throw (new ModelNotFoundException)->setModel('Payment', [$rawId]);
                }

                $activeResolution = $connection
                    ->table(config('payments.tables.resolutions'))
                    ->select(['id_resolucion', 'documento_nuevo'])
                    ->where('raw_pago_id', $rawId)
                    ->where('activo', 1)
                    ->orderByDesc('id_resolucion')
                    ->lockForUpdate()
                    ->first();

                $previousDocument = $activeResolution?->documento_nuevo ?? $rawPayment->DOCUMENTO;

                $this->validateChange($previousDocument, $document, $requiresUnidentified);

                $connection
                    ->table(config('payments.tables.resolutions'))
                    ->where('raw_pago_id', $rawId)
                    ->where('activo', 1)
                    ->update(['activo' => 0]);

                return (int) $connection
                    ->table(config('payments.tables.resolutions'))
                    ->insertGetId([
                        'raw_pago_id' => $rawId,
                        'documento_anterior' => $previousDocument,
                        'documento_nuevo' => $document,
                        'motivo' => $reason,
                        'usuario' => 'user:'.$user->getAuthIdentifier(),
                        'fecha_modificacion' => now('UTC')->format('Y-m-d H:i:s'),
                        'activo' => 1,
                    ], 'id_resolucion');
            }, 3);
        } finally {
            $this->releasePaymentLock($connection, $rawId);
        }
    }

    private function validateChange(?string $previousDocument, string $document, bool $requiresUnidentified): void
    {
        $hasPreviousDocument = filled($previousDocument);

        if ($requiresUnidentified && $hasPreviousDocument) {
            throw ValidationException::withMessages([
                'documento' => 'Este pago ya tiene un documento efectivo. Utiliza la opción Corregir.',
            ]);
        }

        if (! $requiresUnidentified && ! $hasPreviousDocument) {
            throw ValidationException::withMessages([
                'documento' => 'Este pago todavía no tiene documento. Utiliza la opción Identificar.',
            ]);
        }

        if ($hasPreviousDocument && trim((string) $previousDocument) === $document) {
            throw ValidationException::withMessages([
                'documento' => 'El nuevo documento debe ser diferente del documento vigente.',
            ]);
        }
    }

    private function acquirePaymentLock(Connection $connection, int $rawId): void
    {
        if ($connection->getDriverName() !== 'mysql') {
            return;
        }

        $result = $connection->selectOne(
            'SELECT GET_LOCK(?, ?) AS acquired',
            [$this->paymentLockName($rawId), config('payments.resolution_lock_timeout_seconds')],
        );

        if ((int) ($result->acquired ?? 0) !== 1) {
            throw ValidationException::withMessages([
                'documento' => 'Otro usuario está actualizando este pago. Intenta nuevamente.',
            ]);
        }
    }

    private function releasePaymentLock(Connection $connection, int $rawId): void
    {
        if ($connection->getDriverName() !== 'mysql') {
            return;
        }

        $connection->selectOne(
            'SELECT RELEASE_LOCK(?) AS released',
            [$this->paymentLockName($rawId)],
        );
    }

    private function paymentLockName(int $rawId): string
    {
        return 'kpdm:payment-resolution:'.$rawId;
    }

    private function connection(): Connection
    {
        return DB::connection(config('payments.control_connection'));
    }
}
