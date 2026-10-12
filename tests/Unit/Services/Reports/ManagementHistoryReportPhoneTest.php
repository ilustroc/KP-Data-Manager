<?php

namespace Tests\Unit\Services\Reports;

use App\Services\Reports\ManagementHistoryReportPhone;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class ManagementHistoryReportPhoneTest extends TestCase
{
    #[DataProvider('validPhones')]
    public function test_normalizes_valid_mobile_phones(string $source, string $expected): void
    {
        $this->assertSame($expected, (new ManagementHistoryReportPhone)->normalize($source));
    }

    #[DataProvider('invalidPhones')]
    public function test_rejects_nonempty_invalid_phone_sources(string $source): void
    {
        $this->assertFalse((new ManagementHistoryReportPhone)->normalize($source));
    }

    #[DataProvider('emptyPhones')]
    public function test_preserves_rows_with_empty_phone_sources(mixed $source): void
    {
        $this->assertNull((new ManagementHistoryReportPhone)->normalize($source));
    }

    /** @return array<string, array{string, string}> */
    public static function validPhones(): array
    {
        return [
            'plain mobile' => ['934043966', '934043966'],
            'country prefix with plus' => ['+51934043966', '934043966'],
            'country prefix without plus' => ['51934043966', '934043966'],
            'formatted country prefix' => ['51 934 043 966', '934043966'],
            'all allowed format characters' => ['(934) 043-966.*', '934043966'],
        ];
    }

    /** @return array<string, array{string}> */
    public static function invalidPhones(): array
    {
        return [
            'landline' => ['016733123'],
            'short phone' => ['3815686'],
            'letters' => ['934A043966'],
            'unsupported format character' => ['#934043966'],
            'wrong country prefix' => ['52934043966'],
        ];
    }

    /** @return array<string, array{mixed}> */
    public static function emptyPhones(): array
    {
        return [
            'null' => [null],
            'empty' => [''],
            'whitespace' => ['   '],
        ];
    }
}
