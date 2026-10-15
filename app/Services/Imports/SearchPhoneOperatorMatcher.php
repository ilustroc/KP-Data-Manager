<?php

namespace App\Services\Imports;

use JsonException;

final class SearchPhoneOperatorMatcher
{
    private string $pattern;

    public function __construct()
    {
        $path = resource_path('contracts/search-telefonos-v1.json');
        $contents = file_get_contents($path);
        if ($contents === false) {
            throw new SearchImportConfigurationException('No se pudo leer el contrato TELEFONOS v1.');
        }
        try {
            $contract = json_decode($contents, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new SearchImportConfigurationException('El contrato TELEFONOS v1 no contiene JSON válido.', previous: $exception);
        }
        $operators = $contract['operators'] ?? null;
        if (! is_array($operators) || $operators === []) {
            throw new SearchImportConfigurationException('El contrato TELEFONOS v1 no contiene operadores.');
        }
        usort($operators, static fn (string $left, string $right): int => strlen($right) <=> strlen($left));
        $alternatives = array_map(static fn (string $operator): string => preg_quote($operator, '/'), $operators);
        $this->pattern = '/(?<![A-Z0-9])(?:'.implode('|', $alternatives).')(?![A-Z0-9])/u';
    }

    /** @return array{raw: string, operator: string|null, error: string|null} */
    public function match(mixed $value): array
    {
        $raw = preg_replace('/\s+/u', ' ', trim((string) $value)) ?? '';
        $uppercase = mb_strtoupper($raw);
        preg_match_all($this->pattern, $uppercase, $matches);
        $selected = array_fill_keys($matches[0], true);

        if ($selected === []) {
            return ['raw' => $raw, 'operator' => null, 'error' => 'OPERATOR_INVALID'];
        }
        if (count($selected) > 1) {
            return ['raw' => $raw, 'operator' => null, 'error' => 'OPERATOR_AMBIGUOUS'];
        }

        return ['raw' => $raw, 'operator' => array_key_first($selected), 'error' => null];
    }
}
