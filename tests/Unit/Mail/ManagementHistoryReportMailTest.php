<?php

namespace Tests\Unit\Mail;

use App\Mail\ManagementHistoryReportMail;
use DateTimeImmutable;
use DateTimeZone;
use Tests\TestCase;

class ManagementHistoryReportMailTest extends TestCase
{
    public function test_renders_configured_subject_and_report_summary_in_lima_time(): void
    {
        config([
            'reports.management_history.subject' => 'Asunto corporativo de prueba',
            'reports.management_history.timezone' => 'America/Lima',
        ]);
        $mail = new ManagementHistoryReportMail(
            generatedAt: new DateTimeImmutable('2026-10-09 15:30:00', new DateTimeZone('UTC')),
            periodFrom: new DateTimeImmutable('2026-10-01 05:00:00', new DateTimeZone('UTC')),
            periodTo: new DateTimeImmutable('2026-10-09 05:00:00', new DateTimeZone('UTC')),
            recordCount: 1250,
        );

        $mail
            ->assertHasSubject('Asunto corporativo de prueba')
            ->assertSeeInHtml('Reporte histórico de gestiones')
            ->assertSeeInHtml('01/10/2026')
            ->assertSeeInHtml('09/10/2026')
            ->assertSeeInHtml('1,250')
            ->assertSeeInHtml('09/10/2026 10:30');
    }

    public function test_escapes_dynamic_values_rendered_in_the_email(): void
    {
        config(['reports.management_history.subject' => '<script>alert("subject")</script>']);
        $mail = new ManagementHistoryReportMail(
            generatedAt: new DateTimeImmutable('2026-10-09 15:30:00', new DateTimeZone('UTC')),
        );

        $mail->assertHasSubject('<script>alert("subject")</script>');
        $mail->assertDontSeeInHtml('<script>alert("subject")</script>', escape: false);
    }

    public function test_renders_private_drive_link_without_attachment(): void
    {
        $mail = new ManagementHistoryReportMail(
            generatedAt: new DateTimeImmutable('2026-10-09 15:30:00', new DateTimeZone('UTC')),
            periodFrom: new DateTimeImmutable('2025-10-01 05:00:00', new DateTimeZone('UTC')),
            periodTo: new DateTimeImmutable('2026-10-08 05:00:00', new DateTimeZone('UTC')),
            recordCount: 360832,
            filename: 'historico_gestiones.xlsx',
            downloadUrl: 'https://drive.google.com/file/d/private-file-id/view',
        );

        $mail
            ->assertSeeInHtml('01/10/2025')
            ->assertSeeInHtml('08/10/2026')
            ->assertSeeInHtml('360,832')
            ->assertSeeInHtml('historico_gestiones.xlsx')
            ->assertSeeInHtml('DESCARGAR REPORTE')
            ->assertSeeInHtml('https://drive.google.com/file/d/private-file-id/view', escape: false)
            ->assertSeeInHtml('sujeto a los permisos configurados en Google Drive')
            ->assertHasNoAttachments();
    }
}
