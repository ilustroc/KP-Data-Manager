<?php

namespace Tests\Feature\Console;

use App\Mail\ManagementHistoryReportMail;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Mail;
use RuntimeException;
use Tests\TestCase;

class TestManagementHistoryReportMailCommandTest extends TestCase
{
    public function test_sends_mailable_to_configured_recipients_without_real_delivery(): void
    {
        Mail::fake();
        config([
            'reports.management_history.recipients' => 'reportes@kpinvest.pe, operaciones@kpinvest.pe',
        ]);

        $this->artisan('reports:gestiones-mail-test')
            ->expectsOutputToContain('Correo de prueba enviado a 2 destinatario(s).')
            ->assertSuccessful();

        Mail::assertSent(ManagementHistoryReportMail::class, function (ManagementHistoryReportMail $mail): bool {
            return $mail->hasTo('reportes@kpinvest.pe')
                && $mail->hasTo('operaciones@kpinvest.pe');
        });
    }

    public function test_invalid_recipients_fail_controlled_without_sending_mail(): void
    {
        Mail::fake();
        config(['reports.management_history.recipients' => 'correo-invalido']);

        $this->artisan('reports:gestiones-mail-test')
            ->expectsOutputToContain('dirección de correo inválida')
            ->assertFailed();

        Mail::assertNothingSent();
    }

    public function test_missing_recipients_fail_controlled_without_sending_mail(): void
    {
        Mail::fake();
        config(['reports.management_history.recipients' => '']);

        $this->artisan('reports:gestiones-mail-test')
            ->expectsOutputToContain('No hay destinatarios válidos configurados')
            ->assertFailed();

        Mail::assertNothingSent();
    }

    public function test_transport_failure_does_not_expose_exception_secrets(): void
    {
        config(['reports.management_history.recipients' => 'reportes@kpinvest.pe']);
        Mail::shouldReceive('to')
            ->once()
            ->andThrow(new RuntimeException('smtp-password-super-secret'));

        $exitCode = Artisan::call('reports:gestiones-mail-test');
        $output = Artisan::output();

        $this->assertSame(Command::FAILURE, $exitCode);
        $this->assertStringContainsString('No fue posible enviar el correo de prueba', $output);
        $this->assertStringNotContainsString('smtp-password-super-secret', $output);
    }
}
