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
    'registration_types' => ['PAGOS', 'CARTERA', 'SEARCH'],

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

    'private_files' => [
        'enforce_before_dispatch' => filter_var(
            env('IMPORT_ENFORCE_ETL_FILE_ACCESS', true),
            FILTER_VALIDATE_BOOL,
        ),
        'etl_user' => env('IMPORT_ETL_USER'),
        'shared_group' => env('IMPORT_SHARED_GROUP'),
        'file_mode' => intval((string) env('IMPORT_FILE_MODE', '0640'), 8),
        'directory_mode' => intval((string) env('IMPORT_DIRECTORY_MODE', '2750'), 8),
    ],

    'pagination' => [
        'default' => 25,
        'allowed' => [25, 50, 100],
        'errors' => 50,
    ],

    'search' => [
        'type' => 'SEARCH',
        'registration_enabled' => true,
        'control_connection' => 'mysql_control',
        'bronze_connection' => 'mysql_bronze',
        'preview_rows' => 20,
        'preview_error_limit' => 100,
        'preview_ttl_minutes' => 30,
        'available_datasets' => ['PERSONAS', 'TELEFONOS', 'FAMILIA', 'CORREOS', 'DIRECCIONES', 'VEHICULOS', 'PROPIEDADES', 'SBS_RESUMEN', 'SBS_DETALLE', 'LABORAL_ESSALUD'],
        'provisional_source_codes' => [
            'PERSONAS' => 'BASE_PERSONAS',
            'TELEFONOS' => 'BASE_TELEFONOS',
            'FAMILIA' => 'BASE_FAMILIA',
            'CORREOS' => 'BASE_CORREOS',
            'DIRECCIONES' => 'BASE_DIRECCIONES',
            'VEHICULOS' => 'BASE_VEHICULOS',
            'PROPIEDADES' => 'BASE_SUNARP',
            'SBS_RESUMEN' => 'BASE_SBS',
            'SBS_DETALLE' => 'BASE_SBS_DETALLE',
            'LABORAL_ESSALUD' => 'BASE_ESSALUD',
        ],
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
