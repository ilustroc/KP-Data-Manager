<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\GoogleDriveApiErrorContext;
use Google\Service\Exception as GoogleServiceException;
use Tests\TestCase;

class GoogleDriveApiErrorContextTest extends TestCase
{
    public function test_extracts_google_api_status_reason_and_domain(): void
    {
        $exception = new GoogleServiceException(
            'The caller does not have permission.',
            403,
            null,
            [[
                'reason' => 'insufficientPermissions',
                'domain' => 'global',
                'message' => 'Insufficient Permission',
            ]],
        );

        $context = (new GoogleDriveApiErrorContext)->build(
            $exception,
            'upload',
            'remote-file-id',
            true,
        );

        $this->assertSame('upload', $context['operation']);
        $this->assertSame(GoogleServiceException::class, $context['exception_class']);
        $this->assertSame(403, $context['status_code']);
        $this->assertSame(['insufficientPermissions'], $context['google_api_reasons']);
        $this->assertSame(['global'], $context['google_api_domains']);
        $this->assertSame(substr(hash('sha256', 'remote-file-id'), 0, 12), $context['file_reference']);
        $this->assertTrue($context['shared_drive_configured']);
        $this->assertTrue($context['supports_all_drives']);
    }

    public function test_sanitizes_credentials_tokens_and_urls_from_message(): void
    {
        $exception = new GoogleServiceException(
            'private_key=super-secret access_token=token-secret Authorization: Bearer bearer-secret '.
            'client_email=service@example.test {"client_secret":"json-secret"} '.
            'https://www.googleapis.com/drive/v3/files?access_token=query-secret',
            404,
            null,
            [['reason' => 'fileNotFound', 'domain' => 'global']],
        );

        $context = (new GoogleDriveApiErrorContext)->build($exception, 'metadata', null, false);
        $serialized = json_encode($context, JSON_THROW_ON_ERROR);

        $this->assertSame(404, $context['status_code']);
        $this->assertSame(['fileNotFound'], $context['google_api_reasons']);
        $this->assertStringNotContainsString('super-secret', $serialized);
        $this->assertStringNotContainsString('token-secret', $serialized);
        $this->assertStringNotContainsString('bearer-secret', $serialized);
        $this->assertStringNotContainsString('service@example.test', $serialized);
        $this->assertStringNotContainsString('json-secret', $serialized);
        $this->assertStringNotContainsString('googleapis.com', $serialized);
        $this->assertStringNotContainsString('private_key', $serialized);
        $this->assertStringNotContainsString('access_token', $serialized);
        $this->assertStringNotContainsString('client_secret', $serialized);
    }
}
