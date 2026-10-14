<?php

$allowedExtensions = array_values(array_filter(array_map(
    static fn (string $extension): string => strtolower(trim($extension)),
    explode(',', (string) env('IMPORT_ALLOWED_EXTENSIONS', 'csv,xlsx')),
)));

return [
    'connection' => 'mysql_control',
    'table' => 'import_batch',
    'error_table' => 'import_error',

    'storage_disk' => env('IMPORT_STORAGE_DISK', 'imports'),
    'inbox_path' => env('IMPORT_INBOX_PATH') ?: storage_path('app/private/import-inbox'),
    'max_web_upload_mb' => (int) env('IMPORT_MAX_WEB_UPLOAD_MB', 50),
    'allowed_extensions' => $allowedExtensions,
    'registration_types' => ['PAGOS', 'CARTERA'],

    'allowed_mime_types' => [
        'csv' => [
            'text/csv',
            'text/plain',
            'application/csv',
            'application/vnd.ms-excel',
            'text/comma-separated-values',
        ],
        'xlsx' => [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/zip',
            'application/x-zip',
            'application/x-zip-compressed',
        ],
    ],

    'pagination' => [
        'default' => 25,
        'allowed' => [25, 50, 100],
        'errors' => 50,
    ],

    'search' => [
        'type' => 'SEARCH',
        'registration_enabled' => false,
        'control_connection' => 'mysql_control',
        'bronze_connection' => 'mysql_bronze',
        'scope_insert_chunk_size' => 1000,
        'tables' => [
            'datasets' => 'import_dataset',
            'sources' => 'import_source',
            'dataset_sources' => 'import_dataset_source',
            'column_mappings' => 'import_column_mapping',
            'scope_documents' => 'import_scope_document',
            'raw_rows' => 'search_raw_row',
        ],
    ],

    'deletion' => [
        'audit_table' => 'import_deletion_log',
        'entity_tables' => [
            'BBVA' => [
                'kp_silver.cartera_contactos',
                'kp_silver.cartera_direcciones',
                'kp_silver.cartera_operaciones',
                'kp_bronze.raw_cartera_bbva',
            ],
            'CAJA_AREQUIPA' => [
                'kp_silver.cartera_caja_arequipa_detalle',
                'kp_silver.cartera_avales',
                'kp_silver.cartera_garantias',
                'kp_silver.cartera_contactos',
                'kp_silver.cartera_direcciones',
                'kp_silver.cartera_operaciones',
                'kp_bronze.raw_cartera_caja_arequipa',
            ],
            'COMPARTAMOS' => [
                'kp_silver.cartera_compartamos_detalle',
                'kp_silver.cartera_contactos',
                'kp_silver.cartera_direcciones',
                'kp_silver.cartera_operaciones',
                'kp_bronze.raw_cartera_compartamos',
            ],
            'CONFIANZA' => [
                'kp_silver.cartera_confianza_detalle',
                'kp_silver.cartera_contactos',
                'kp_silver.cartera_direcciones',
                'kp_silver.cartera_operaciones',
                'kp_bronze.raw_cartera_confianza',
            ],
            'WANDOO' => [
                'kp_silver.cartera_wandoo_detalle',
                'kp_silver.cartera_direcciones',
                'kp_silver.cartera_operaciones',
                'kp_bronze.raw_cartera_wandoo',
            ],
        ],
    ],
];
