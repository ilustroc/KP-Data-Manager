<?php

namespace Tests\Unit;

use App\Services\Imports\SearchPhoneOperatorMatcher;
use Tests\TestCase;

class SearchPhoneOperatorMatcherTest extends TestCase
{
    public function test_it_matches_the_canonical_operator_anywhere_with_longest_phrase_precedence(): void
    {
        $matcher = app(SearchPhoneOperatorMatcher::class);
        $examples = [
            'SEPTIEMBRE MOVISTAR 2020' => 'MOVISTAR',
            '2020 MOVISTAR SEPTIEMBRE' => 'MOVISTAR',
            'DATA CLARO AGOSTO 2026' => 'CLARO',
            'JULIO ENTEL 2026' => 'ENTEL',
            'ENERO FLASH MOBILE 2026' => 'FLASH MOBILE',
            'ENERO GUINEA MOBILE 2026' => 'GUINEA MOBILE',
            'MOVISTAR NOVIEMBRE 2024' => 'MOVISTAR',
            'BITEL DICIEMBRE 2025' => 'BITEL',
            'MINSA MARZO 2026' => 'MINSA',
        ];

        foreach ($examples as $raw => $expected) {
            $result = $matcher->match($raw);
            $this->assertSame($expected, $result['operator']);
            $this->assertNull($result['error']);
        }
    }

    public function test_it_normalizes_whitespace_and_respects_word_boundaries(): void
    {
        $matcher = app(SearchPhoneOperatorMatcher::class);

        $result = $matcher->match('  SEPTIEMBRE   MOVISTAR   2020  ');
        $this->assertSame('SEPTIEMBRE MOVISTAR 2020', $result['raw']);
        $this->assertSame('MOVISTAR', $result['operator']);
        $this->assertSame('OPERATOR_INVALID', $matcher->match('PREMOVISTARX 2020')['error']);
    }

    public function test_it_rejects_ambiguous_and_unknown_values(): void
    {
        $matcher = app(SearchPhoneOperatorMatcher::class);

        $this->assertSame('OPERATOR_AMBIGUOUS', $matcher->match('MOVISTAR CLARO 2025')['error']);
        $this->assertSame('OPERATOR_INVALID', $matcher->match('OPERADOR INVENTADO 2025')['error']);
    }
}
