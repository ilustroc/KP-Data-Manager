<?php

return [
    'enabled' => filter_var(env('ETL_ENABLED', false), FILTER_VALIDATE_BOOL),
    'python_binary' => env('ETL_PYTHON_BINARY', ''),
    'workdir' => env('ETL_WORKDIR', ''),
    'process_timeout_seconds' => (int) env('ETL_PROCESS_TIMEOUT_SECONDS', 3600),
    'job_timeout_seconds' => (int) env('ETL_JOB_TIMEOUT_SECONDS', 3660),
    'queue' => env('ETL_QUEUE', 'etl'),
];
