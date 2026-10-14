<?php

namespace Tests\Unit\Database;

use PHPUnit\Framework\TestCase;

class SearchInfrastructureSqlTest extends TestCase
{
    public function test_catalog_sql_creates_only_the_approved_control_catalogs(): void
    {
        $sql = $this->sql('024_create_search_import_catalogs.sql');

        $this->assertStringContainsString('CREATE TABLE `kp_control`.`import_dataset`', $sql);
        $this->assertStringContainsString('CREATE TABLE `kp_control`.`import_source`', $sql);
        $this->assertStringContainsString('CREATE TABLE `kp_control`.`import_dataset_source`', $sql);
        $this->assertSame(11, substr_count($sql, 'UTC_TIMESTAMP(), UTC_TIMESTAMP())'));
        foreach ([
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
        ] as $datasetCode) {
            $this->assertStringContainsString("('{$datasetCode}'", $sql);
        }
    }

    public function test_import_batch_evolution_is_nullable_and_uses_composite_idempotency(): void
    {
        $sql = $this->sql('025_extend_import_batch_for_search.sql');

        foreach ([
            'dataset_code',
            'source_code',
            'refresh_mode',
            'rows_valid',
            'rows_invalid',
            'rows_published',
            'scope_count',
            'received_at',
            'validated_at',
            'published_at',
            'uploaded_by_user_id',
            'mapping_version',
            'idempotency_key',
        ] as $column) {
            $this->assertMatchesRegularExpression(
                '/ADD COLUMN `'.preg_quote($column, '/').'`[^,]+ NULL(?: AFTER|,)/',
                $sql,
            );
        }

        $this->assertStringContainsString(
            'ADD UNIQUE KEY `uq_import_batch_idempotency_key` (`idempotency_key`)',
            $sql,
        );
        $this->assertDoesNotMatchRegularExpression('/UNIQUE KEY[^\n]+archivo_sha256/', $sql);
        $this->assertStringNotContainsString('DROP COLUMN', strtoupper($sql));
    }

    public function test_mapping_and_scope_sql_define_exact_scope_uniqueness_without_silver_tables(): void
    {
        $sql = $this->sql('026_create_search_mapping_and_scope.sql');

        $this->assertStringContainsString('CREATE TABLE `kp_control`.`import_column_mapping`', $sql);
        $this->assertStringContainsString('CREATE TABLE `kp_control`.`import_scope_document`', $sql);
        $this->assertStringContainsString(
            'UNIQUE KEY `uq_import_scope_document_batch` (`batch_id`, `documento`)',
            $sql,
        );
        $this->assertStringContainsString('`source_position` SMALLINT UNSIGNED NOT NULL', $sql);
        $this->assertStringNotContainsString('kp_silver', strtolower($sql));
        $this->assertStringNotContainsString('kp_gold', strtolower($sql));
    }

    public function test_search_bronze_is_generic_append_only_json_with_non_unique_hash(): void
    {
        $sql = $this->sql('027_create_search_raw_row.sql');

        $this->assertStringContainsString('CREATE TABLE `kp_bronze`.`search_raw_row`', $sql);
        $this->assertStringContainsString('`raw_payload` JSON NOT NULL', $sql);
        $this->assertStringContainsString('`row_hash` CHAR(64)', $sql);
        $this->assertStringContainsString('KEY `idx_search_raw_row_hash` (`row_hash`)', $sql);
        $this->assertDoesNotMatchRegularExpression('/UNIQUE KEY[^\n]+row_hash/', $sql);
        $this->assertDoesNotMatchRegularExpression('/^\s*(UPDATE|DELETE|DROP|TRUNCATE)\b/im', $sql);
    }

    public function test_dm_f1_sql_avoids_mysql_8_only_features_and_final_search_tables(): void
    {
        $sql = implode("\n", [
            $this->sql('024_create_search_import_catalogs.sql'),
            $this->sql('025_extend_import_batch_for_search.sql'),
            $this->sql('026_create_search_mapping_and_scope.sql'),
            $this->sql('027_create_search_raw_row.sql'),
        ]);

        foreach (['JSON_TABLE', 'WITH RECURSIVE', 'ROW_NUMBER(', 'CREATE ROLE'] as $unsupported) {
            $this->assertStringNotContainsString($unsupported, strtoupper($sql));
        }

        foreach (['search_personas', 'search_telefonos', 'search_person_index'] as $futureTable) {
            $this->assertStringNotContainsString("CREATE TABLE `kp_silver`.`{$futureTable}`", $sql);
            $this->assertStringNotContainsString("CREATE TABLE `kp_gold`.`{$futureTable}`", $sql);
        }
    }

    private function sql(string $filename): string
    {
        $contents = file_get_contents(dirname(__DIR__, 3).'/database/sql/'.$filename);

        $this->assertNotFalse($contents);

        return $contents;
    }
}
