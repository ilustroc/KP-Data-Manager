<?php

return [
    'connection' => 'mysql_silver',

    'views' => [
        'current' => 'v_pagos_actuales',
        'unidentified' => 'v_pagos_sin_identificar',
    ],

    'pagination' => [
        'default' => 25,
        'allowed' => [25, 50, 100],
    ],
];
