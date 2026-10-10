<?php

return [
    'management_history' => [
        'recipients' => env('GESTIONES_REPORT_RECIPIENTS', ''),
        'subject' => env('GESTIONES_REPORT_SUBJECT', 'Reporte histórico de gestiones'),
        'filename_prefix' => 'historico_gestiones',
        'timezone' => 'America/Lima',
        'source_timezone' => 'UTC',
        'connection' => 'mysql_control',
        'table' => 'kpinvest_konnexia.cob_gestiones',
        'temporary_directory' => storage_path('app/private/reports'),
        'drive' => [
            'enabled' => filter_var(env('GESTIONES_REPORT_DRIVE_ENABLED', false), FILTER_VALIDATE_BOOL),
            'credentials_path' => env('GOOGLE_DRIVE_REPORT_CREDENTIALS_PATH', ''),
            'folder_id' => env('GOOGLE_DRIVE_REPORT_FOLDER_ID', ''),
            'shared_drive_id' => env('GOOGLE_DRIVE_REPORT_SHARED_DRIVE_ID', ''),
            'filename' => env('GOOGLE_DRIVE_REPORT_FILENAME', 'historico_gestiones.xlsx'),
            'chunk_size_bytes' => (int) env('GOOGLE_DRIVE_REPORT_CHUNK_MB', 5) * 1024 * 1024,
        ],
    ],
];
