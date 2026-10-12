<?php

namespace App\Services\Reports;

use Google\Service\Exception as GoogleServiceException;
use Illuminate\Support\Str;
use Throwable;

class GoogleDriveApiErrorContext
{
    /**
     * @return array{
     *     operation: string,
     *     exception_class: class-string<Throwable>,
     *     status_code: ?int,
     *     google_api_reasons: list<string>,
     *     google_api_domains: list<string>,
     *     message: string,
     *     file_reference: ?string,
     *     shared_drive_configured: bool,
     *     supports_all_drives: bool
     * }
     */
    public function build(
        Throwable $exception,
        string $operation,
        ?string $fileId,
        bool $sharedDriveConfigured,
    ): array {
        $reasons = [];
        $domains = [];

        if ($exception instanceof GoogleServiceException) {
            foreach ($exception->getErrors() ?? [] as $error) {
                $reason = $this->safeApiIdentifier($error['reason'] ?? null);
                $domain = $this->safeApiIdentifier($error['domain'] ?? null);

                if ($reason !== null) {
                    $reasons[] = $reason;
                }

                if ($domain !== null) {
                    $domains[] = $domain;
                }
            }
        }

        return [
            'operation' => $operation,
            'exception_class' => $exception::class,
            'status_code' => $exception->getCode() > 0 ? $exception->getCode() : null,
            'google_api_reasons' => array_values(array_unique($reasons)),
            'google_api_domains' => array_values(array_unique($domains)),
            'message' => $this->sanitizeMessage($exception->getMessage()),
            'file_reference' => $fileId === null ? null : substr(hash('sha256', $fileId), 0, 12),
            'shared_drive_configured' => $sharedDriveConfigured,
            'supports_all_drives' => true,
        ];
    }

    private function safeApiIdentifier(mixed $value): ?string
    {
        if (! is_string($value) || ! preg_match('/\A[A-Za-z0-9_.-]{1,100}\z/', $value)) {
            return null;
        }

        return $value;
    }

    private function sanitizeMessage(string $message): string
    {
        $sanitized = preg_replace(
            '/-----BEGIN [^-]+-----.*?-----END [^-]+-----/s',
            '[sensitive value redacted]',
            $message,
        ) ?? '';
        $sanitized = preg_replace(
            '/\bAuthorization\b\s*[:=]\s*(?:Bearer\s+)?[^\s,;]+/i',
            '[sensitive header redacted]',
            $sanitized,
        ) ?? '';
        $sanitized = preg_replace('/\bBearer\s+[^\s,;]+/i', '[token redacted]', $sanitized) ?? '';
        $sanitized = preg_replace(
            '/["\']?(?:private_key|private_key_id|access_token|refresh_token|authorization|credentials|client_secret|client_email)["\']?\s*[:=]\s*(?:"(?:\\\\.|[^"])*"|\'(?:\\\\.|[^\'])*\'|[^\s,;]+)/i',
            '[sensitive value redacted]',
            $sanitized,
        ) ?? '';
        $sanitized = preg_replace('/https?:\/\/[^\s]+/i', '[url omitted]', $sanitized) ?? '';
        $sanitized = preg_replace('/[\r\n\t]+/', ' ', $sanitized) ?? '';

        return Str::limit(trim($sanitized), 1000, '…');
    }
}
