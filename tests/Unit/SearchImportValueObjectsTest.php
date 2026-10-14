<?php

namespace Tests\Unit;

use App\DatasetCode;
use App\RefreshMode;
use App\SearchSourceCode;
use App\Services\Imports\SearchImportIdempotencyKey;
use InvalidArgumentException;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class SearchImportValueObjectsTest extends TestCase
{
    public function test_dataset_catalog_contains_the_eleven_approved_codes(): void
    {
        $this->assertSame([
            'PERSONAS',
            'TELEFONOS',
            'FAMILIA',
            'DIRECCIONES',
            'LABORAL_ESSALUD',
            'VEHICULOS',
            'CORREOS',
            'SUNAT',
            'SBS_RESUMEN',
            'SBS_DETALLE',
            'PROPIEDADES',
        ], array_column(DatasetCode::cases(), 'value'));
    }

    public function test_refresh_modes_are_explicit_and_map_to_permission_columns(): void
    {
        $this->assertSame('allows_full_replace', RefreshMode::FullReplace->permissionColumn());
        $this->assertSame('allows_scope_replace', RefreshMode::ScopeReplace->permissionColumn());
        $this->assertSame('allows_upsert', RefreshMode::Upsert->permissionColumn());
    }

    public function test_source_code_is_dynamic_normalized_and_not_an_enum(): void
    {
        $source = SearchSourceCode::from(' proveedor-nuevo_2026 ');

        $this->assertSame('PROVEEDOR-NUEVO_2026', $source->value);
        $this->assertSame('PROVEEDOR-NUEVO_2026', (string) $source);
    }

    #[DataProvider('invalidSourceCodes')]
    public function test_invalid_source_code_is_rejected(string $value): void
    {
        $this->expectException(InvalidArgumentException::class);

        SearchSourceCode::from($value);
    }

    public function test_idempotency_key_is_stable_and_includes_every_search_dimension(): void
    {
        $service = new SearchImportIdempotencyKey;
        $source = SearchSourceCode::from('RENIEC');
        $sha256 = str_repeat('a', 64);
        $base = $service->make(
            DatasetCode::Personas,
            $source,
            RefreshMode::FullReplace,
            '1',
            2,
            $sha256,
        );

        $this->assertSame($base, $service->make(
            DatasetCode::Personas,
            $source,
            RefreshMode::FullReplace,
            '1',
            2,
            strtoupper($sha256),
        ));
        $this->assertNotSame($base, $service->make(
            DatasetCode::Telefonos,
            $source,
            RefreshMode::FullReplace,
            '1',
            2,
            $sha256,
        ));
        $this->assertNotSame($base, $service->make(
            DatasetCode::Personas,
            SearchSourceCode::from('OTRA_FUENTE'),
            RefreshMode::FullReplace,
            '1',
            2,
            $sha256,
        ));
        $this->assertNotSame($base, $service->make(
            DatasetCode::Personas,
            $source,
            RefreshMode::ScopeReplace,
            '1',
            2,
            $sha256,
        ));
        $this->assertNotSame($base, $service->make(
            DatasetCode::Personas,
            $source,
            RefreshMode::FullReplace,
            '2',
            2,
            $sha256,
        ));
        $this->assertNotSame($base, $service->make(
            DatasetCode::Personas,
            $source,
            RefreshMode::FullReplace,
            '1',
            3,
            $sha256,
        ));
        $this->assertNotSame($base, $service->make(
            DatasetCode::Personas,
            $source,
            RefreshMode::FullReplace,
            '1',
            2,
            str_repeat('b', 64),
        ));
    }

    public function test_invalid_file_hash_is_rejected(): void
    {
        $this->expectException(InvalidArgumentException::class);

        (new SearchImportIdempotencyKey)->make(
            DatasetCode::Personas,
            SearchSourceCode::from('RENIEC'),
            RefreshMode::FullReplace,
            '1',
            1,
            'no-es-sha256',
        );
    }

    /**
     * @return array<string, array{string}>
     */
    public static function invalidSourceCodes(): array
    {
        return [
            'vacío' => [''],
            'espacios' => ['FUENTE CON ESPACIOS'],
            'unicode' => ['FUÉNTE'],
            'demasiado largo' => [str_repeat('A', 65)],
        ];
    }
}
