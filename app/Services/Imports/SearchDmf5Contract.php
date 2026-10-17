<?php

namespace App\Services\Imports;

use RuntimeException;

final readonly class SearchDmf5Contract
{
    /** @var array<string, mixed> */
    private array $values;

    public function __construct()
    {
        $contents = file_get_contents(resource_path('contracts/search-dm-f5-v1.json'));
        $values = $contents === false ? null : json_decode($contents, true, flags: JSON_THROW_ON_ERROR);
        if (! is_array($values)) {
            throw new RuntimeException('No se pudo cargar el contrato SEARCH DM-F5.');
        }
        $this->values = $values;
    }

    /** @return list<string> */
    public function sbsConditions(): array
    {
        return $this->values['sbs_conditions'];
    }

    public function periodPattern(): string
    {
        return $this->values['period_pattern'];
    }

    /** @return array<string, string|bool> */
    public function shiftedDetailFields(): array
    {
        return $this->values['sbs_detail_shift'];
    }
}
