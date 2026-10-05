# KP Data Manager ETL — Fase 5

Motor CLI para procesar batches `PENDIENTE` de tipo `PAGOS` hacia `kp_bronze.raw_pagos`. Esta fase no incluye scheduler, Supervisor, systemd ni ejecución desde Laravel.

## Runtime

El código requiere Python 3.11 o superior. El runtime definitivo del VPS legacy se resolverá en una fase posterior sin modificar el Python del sistema Ubuntu 16.04.

Desarrollo local:

```powershell
cd etl
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Linux con un runtime moderno instalado de forma aislada:

```bash
cd etl
/ruta/python3.11 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

`.venv` y `.env` están excluidos de Git.

## Configuración

Configurar `etl/.env` sin guardar credenciales en el repositorio:

```dotenv
ETL_DB_HOST=127.0.0.1
ETL_DB_PORT=3306
ETL_DB_USERNAME=kp_data_manager_etl
ETL_DB_PASSWORD=
ETL_CONTROL_DATABASE=kp_control
ETL_BRONZE_DATABASE=kp_bronze
ETL_IMPORT_STORAGE_ROOT=../storage/app/private/imports
ETL_INSERT_BATCH_SIZE=5000
ETL_PROGRESS_UPDATE_EVERY=5000
ETL_ALLOW_ZERO_AMOUNT=true
ETL_ERROR_VALUE_MAX_LENGTH=500
ETL_LOG_LEVEL=INFO
```

El worker rechaza explícitamente `root`, `jesus_admin` y `kp_data_manager_app`. El usuario ETL debe crearse posteriormente con permisos mínimos:

- `SELECT`, `UPDATE` sobre `kp_control.import_batch`.
- `INSERT` sobre `kp_control.import_error`.
- `INSERT` sobre `kp_bronze.raw_pagos`.

No necesita `DELETE` ni `UPDATE` sobre Bronze.

## DDL requerido

Antes de una prueba manual deben haberse revisado y aplicado manualmente:

1. `database/sql/001_create_import_error.sql`.
2. `database/sql/002_extend_import_batch_file_metadata.sql`.
3. `database/sql/003_add_raw_pagos_row_hash.sql`.
4. `database/sql/007_align_raw_pagos_batch_id.sql`.

`003` agrega una huella técnica con índice **no único**. El ETL calcula `row_hash`, pero no consulta esa columna ni descarta coincidencias. `007` alinea `raw_pagos.batch_id` con `import_batch.batch_id` como `BIGINT UNSIGNED NULL` e incorpora un índice no único, sin foreign key entre esquemas.

## Ejecución

Desde `etl/`:

```bash
./.venv/bin/python -m src.worker --batch-id 123
```

En Windows:

```powershell
.\.venv\Scripts\python.exe -m src.worker --batch-id 123
```

El argumento es únicamente el identificador numérico. La ruta se obtiene de `import_batch`; el CLI no acepta rutas de archivos.

## Flujo del batch

1. Lee el batch y exige tipo `PAGOS` y estado `PENDIENTE`.
2. Resuelve `archivo_ruta` dentro de `ETL_IMPORT_STORAGE_ROOT`, sin permitir rutas absolutas, `..` ni symlinks externos.
3. Verifica existencia, extensión y SHA-256 contra los metadatos de Fase 4.
4. Reclama el batch atómicamente como `PROCESANDO` y reinicia sus contadores.
5. Lee CSV o XLSX como iterador.
6. Normaliza y valida cada fila.
7. Inserta pagos y errores con `executemany` en transacciones cortas de aproximadamente `ETL_INSERT_BATCH_SIZE` filas.
8. Actualiza contadores periódicamente.
9. Finaliza como `COMPLETADO`, `COMPLETADO_CON_ERRORES` o `ERROR`, siempre con fechas UTC.

Una caída no borra chunks ya confirmados. Las filas quedan trazables por `batch_id`; una futura operación controlada de rollback podría localizarlas con `WHERE batch_id = X`, pero esta fase no implementa borrados ni reprocesamiento.

Los contadores persistidos representan únicamente chunks confirmados. Si falla el chunk actual, su transacción se revierte y no se suma a los contadores del batch.

## Formatos y normalización

Columnas obligatorias: `FECHA`, `MONTO`, `RECAUDO`.

Columnas opcionales: `DOCUMENTO`, `ACUMULADO`, `OPERACION`, `COMENTARIO`, `HORA`. Si faltan del encabezado se cargan como `NULL`.

- Los encabezados se normalizan con `trim` y mayúsculas.
- CSV se procesa en UTF-8 o UTF-8 con BOM y detecta `;` o `,`. Un encoding inválido produce un error estructural diagnosticado y estado `ERROR`.
- XLSX usa `openpyxl` con `read_only=True` y `data_only=True`.
- `DOCUMENTO` y `OPERACION` son texto. No se aplica LPAD en Bronze.
- Una celda Excel numérica se representa sin notación científica. Solo se recuperan ceros visibles cuando el `number_format` es inequívocamente una máscara compuesta exclusivamente por ceros, por ejemplo `0000000`. No se inventan ceros con formato `General`.
- `MONTO` y `ACUMULADO` usan `Decimal`, con máximo dos decimales y rango `DECIMAL(15,2)`.
- El monto cero es válido por defecto. Puede rechazarse con `ETL_ALLOW_ZERO_AMOUNT=false`. Los importes negativos se conservan para no perder posibles reversos recibidos.
- `ACUMULADO` vacío permanece `NULL` y nunca se recalcula.
- `HORA` admite `HH:MM` y `HH:MM:SS`; ausente permanece `NULL`.
- `COMENTARIO` mayor de 260 caracteres invalida la fila y nunca se trunca.

## Errores y contadores

Una fila inválida no detiene el archivo. Puede generar varios registros en `import_error`, uno por campo. `filas_error` cuenta filas inválidas, no la cantidad de mensajes. El valor capturado en el error está limitado por `ETL_ERROR_VALUE_MAX_LENGTH`.

Los errores estructurales o fatales dejan `mensaje_error` en el batch. Las filas válidas de chunks confirmados previamente permanecen en Bronze con el mismo `batch_id`.

## Pruebas

Desde `etl/`:

```bash
./.venv/bin/python -m pytest
```

Las pruebas usan fakes y archivos temporales; no abren conexiones a MySQL ni contienen datos personales reales.
