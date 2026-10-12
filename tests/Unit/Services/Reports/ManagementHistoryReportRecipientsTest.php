<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\InvalidReportRecipients;
use App\Services\Reports\ManagementHistoryReportRecipients;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class ManagementHistoryReportRecipientsTest extends TestCase
{
    public function test_parses_one_recipient(): void
    {
        $recipients = (new ManagementHistoryReportRecipients)->parse('reportes@kpinvest.pe');

        $this->assertSame(['reportes@kpinvest.pe'], $recipients);
    }

    public function test_parses_multiple_comma_separated_recipients(): void
    {
        $recipients = (new ManagementHistoryReportRecipients)->parse(
            'reportes@kpinvest.pe,operaciones@kpinvest.pe',
        );

        $this->assertSame([
            'reportes@kpinvest.pe',
            'operaciones@kpinvest.pe',
        ], $recipients);
    }

    public function test_removes_case_insensitive_duplicates_and_preserves_first_address(): void
    {
        $recipients = (new ManagementHistoryReportRecipients)->parse(
            'Reportes@kpinvest.pe, reportes@kpinvest.pe',
        );

        $this->assertSame(['Reportes@kpinvest.pe'], $recipients);
    }

    public function test_ignores_surrounding_whitespace_and_empty_entries(): void
    {
        $recipients = (new ManagementHistoryReportRecipients)->parse(
            '  reportes@kpinvest.pe , , operaciones@kpinvest.pe  ,',
        );

        $this->assertSame([
            'reportes@kpinvest.pe',
            'operaciones@kpinvest.pe',
        ], $recipients);
    }

    #[DataProvider('invalidRecipientConfigurations')]
    public function test_rejects_invalid_recipient_addresses(string $configured): void
    {
        $this->expectException(InvalidReportRecipients::class);
        $this->expectExceptionMessage('contiene una dirección de correo inválida');

        (new ManagementHistoryReportRecipients)->parse($configured);
    }

    public function test_fails_when_no_recipient_is_configured(): void
    {
        $this->expectException(InvalidReportRecipients::class);
        $this->expectExceptionMessage('No hay destinatarios válidos configurados');

        (new ManagementHistoryReportRecipients)->parse(' ,  , ');
    }

    /**
     * @return array<string, array{string}>
     */
    public static function invalidRecipientConfigurations(): array
    {
        return [
            'only invalid address' => ['correo-invalido'],
            'invalid mixed with valid' => ['reportes@kpinvest.pe,correo-invalido'],
        ];
    }
}
