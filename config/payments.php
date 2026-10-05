<?php

$bronzeDatabase = env('DB_BRONZE_DATABASE', 'kp_bronze');
$silverDatabase = env('DB_SILVER_DATABASE', 'kp_silver');
$controlDatabase = env('DB_CONTROL_DATABASE', 'kp_control');

return [
    'connection' => 'mysql_silver',
    'control_connection' => 'mysql_control',
    'resolution_lock_timeout_seconds' => 5,

    'views' => [
        'current' => 'v_pagos_actuales',
        'unidentified' => 'v_pagos_sin_identificar',
    ],

    'tables' => [
        'raw' => $bronzeDatabase.'.raw_pagos',
        'resolutions' => $controlDatabase.'.pago_documento_resolucion',
        'audit_current' => $silverDatabase.'.v_pagos_actuales',
    ],

    'pagination' => [
        'default' => 25,
        'allowed' => [25, 50, 100],
    ],
];
