# KP Data Manager ETL

Motor CLI para procesar cargas `PENDIENTE`. Mantiene el loader de `PAGOS` y routing explícito para `CARTERA / BBVA / v1` y `CARTERA / CAJA_AREQUIPA / v1`. El CLI continúa siendo independiente y puede ser invocado por el Queue Job de Laravel sin compartir las credenciales MySQL de ambas aplicaciones.

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
ETL_SILVER_DATABASE=kp_silver
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
- `INSERT`, `SELECT` sobre `kp_bronze.raw_cartera_bbva` para correlacionar `source_row` con `raw_id` dentro del chunk.
- `INSERT`, `SELECT` sobre `kp_bronze.raw_cartera_caja_arequipa` para la misma correlación por chunk.
- `INSERT`, `SELECT` sobre `kp_silver.cartera_operaciones`.
- `INSERT` sobre `kp_silver.cartera_contactos` y `kp_silver.cartera_direcciones`.
- `INSERT` sobre `kp_silver.cartera_caja_arequipa_detalle`, `kp_silver.cartera_avales` y `kp_silver.cartera_garantias`.

No necesita `DELETE` ni `UPDATE` sobre Bronze.

## DDL requerido

Antes de una prueba manual deben haberse revisado y aplicado manualmente:

1. `database/sql/001_create_import_error.sql`.
2. `database/sql/002_extend_import_batch_file_metadata.sql`.
3. `database/sql/003_add_raw_pagos_row_hash.sql`.
4. `database/sql/007_align_raw_pagos_batch_id.sql`.
5. `database/sql/008_extend_import_batch_for_portfolios.sql`.
6. `database/sql/009_create_raw_cartera_bbva.sql`.
7. `database/sql/010_create_cartera_operaciones.sql`.
8. `database/sql/011_create_cartera_contactos.sql`.
9. `database/sql/012_create_cartera_direcciones.sql`.
10. `database/sql/013_create_raw_cartera_caja_arequipa.sql`.
11. `database/sql/014_create_cartera_caja_arequipa_detalle.sql`.
12. `database/sql/015_create_cartera_avales.sql`.
13. `database/sql/016_create_cartera_garantias.sql`.

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

## Integración con la cola de Laravel

Laravel solo encola el identificador del batch. El Job ejecuta el mismo módulo CLI con una lista estructurada de argumentos; no procesa filas ni lee `etl/.env`. Python carga sus propias credenciales desde ese archivo.

Configurar en el `.env` de Laravel, sin incluir credenciales ETL:

```dotenv
ETL_ENABLED=true
ETL_PYTHON_BINARY=C:\ruta\al\proyecto\etl\.venv\Scripts\python.exe
ETL_WORKDIR=C:\ruta\al\proyecto\etl
ETL_PROCESS_TIMEOUT_SECONDS=3600
ETL_QUEUE=etl
DB_QUEUE_RETRY_AFTER=3660
```

En Linux futuro, `ETL_PYTHON_BINARY` podrá apuntar al Python aislado, por ejemplo `/opt/kp-data-etl/.venv/bin/python`. Fase 6 no instala ni configura ese runtime en el VPS.

Iniciar el worker local desde la raíz Laravel:

```bash
php artisan queue:work --queue=etl
```

`DB_QUEUE_RETRY_AFTER` debe superar el timeout máximo del Job para impedir una segunda reserva mientras el proceso sigue activo. `ETL_PROCESS_TIMEOUT_SECONDS=0` desactiva el timeout del proceso, pero exige configurar `DB_QUEUE_RETRY_AFTER` por encima de la duración máxima operacional esperada.

## Flujo del batch

1. Lee la carga y exige estado `PENDIENTE`.
2. Resuelve el loader con un registry: `PAGOS` conserva su loader; Carteras admite los perfiles registrados BBVA v1 y Caja Arequipa v1. Cualquier combinación no registrada se rechaza.
3. Resuelve `archivo_ruta` dentro de `ETL_IMPORT_STORAGE_ROOT`, sin permitir rutas absolutas, `..` ni symlinks externos.
4. Verifica existencia, extensión y SHA-256 contra los metadatos registrados.
5. Reclama la carga atómicamente como `PROCESANDO` y reinicia sus contadores.
6. Lee CSV o XLSX como iterador.
7. Normaliza y valida cada fila.
8. Inserta por `executemany` en transacciones cortas de aproximadamente `ETL_INSERT_BATCH_SIZE` filas.
9. Actualiza contadores periódicamente.
10. Finaliza como `COMPLETADO`, `COMPLETADO_CON_ERRORES` o `ERROR`, siempre con fechas UTC.

### Carteras: BBVA v1 y Caja Arequipa v1

El perfil se identifica por la terna `tipo=CARTERA`, `entidad=BBVA`, `perfil_version=1`. Los encabezados BBVA v1 son estrictos: un encabezado obligatorio ausente, duplicado o adicional indica un formato incompatible y detiene la carga antes de insertar filas. Los cambios de formato deben incorporarse como una nueva versión, nunca reinterpretando silenciosamente una carga histórica.

Cada fila válida se confirma en una única transacción de chunk:

1. Inserción fiel en `kp_bronze.raw_cartera_bbva`.
2. Consulta agrupada por `batch_id + source_row` para obtener `raw_id`.
3. Inserción homologada en `kp_silver.cartera_operaciones`.
4. Consulta agrupada de las operaciones insertadas.
5. Inserción normalizada de teléfonos y dirección.

No se ejecutan `SELECT` ni `INSERT` individuales por fila. Si falla cualquier paso, se revierte el chunk completo. Los chunks anteriores permanecen confirmados, igual que en Pagos.

Mapeo de identidad BBVA confirmado:

- `numdoc` → `documento_cliente`.
- `CODCENTRAL` → `cuenta`.
- `CONTRATO` → `operacion`.
- `DOCUMENTO` → `identificador_origen`; nunca reemplaza los tres campos anteriores.

`deuda_total` permanece `NULL`: no se deriva de capital, interés y mora sin una definición de negocio aprobada. Los cinco bloques de teléfonos se expanden a filas y la dirección BBVA se registra como `PRINCIPAL`. `row_hash` es una huella SHA-256 no única y no elimina registros.

Caja Arequipa v1 exige 66 posiciones exactas, termina en `COSECHA` y conserva por separado las dos columnas fuente llamadas `NRO_DOC_TIT`. Su documento efectivo requiere coincidencia o usa la única ocurrencia informada. Como la fuente no incluye un identificador adicional, `cartera_operaciones.identificador_origen` queda `NULL`. Las fechas numéricas se convierten con el epoch del workbook, los teléfonos `TEL_TIT` y `TEL_GES` se expanden por `|`, y los datos específicos se distribuyen entre detalle, avales y hasta seis garantías. Todas las escrituras de una fila válida permanecen dentro de la transacción corta del chunk.

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
