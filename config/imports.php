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
