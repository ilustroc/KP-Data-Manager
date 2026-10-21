# KP Data Manager ETL

Motor CLI para procesar cargas `PENDIENTE`. Mantiene el loader de `PAGOS` y routing explícito para `CARTERA / BBVA / v1`, `CARTERA / CAJA_AREQUIPA / v1`, `CARTERA / COMPARTAMOS / v1`, `CARTERA / CONFIANZA / v1` y `CARTERA / WANDOO / v1`. El CLI continúa siendo independiente y puede ser invocado por el Queue Job de Laravel sin compartir las credenciales MySQL de ambas aplicaciones.

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
ETL_DB_CONNECT_TIMEOUT=15
ETL_DB_READ_TIMEOUT=600
ETL_DB_WRITE_TIMEOUT=600
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

`ETL_DB_READ_TIMEOUT` y `ETL_DB_WRITE_TIMEOUT` son límites del cliente PyMySQL. En particular, `ETL_DB_READ_TIMEOUT` controla cuánto espera el ETL por la respuesta de una operación MySQL extensa; no modifica `wait_timeout` ni ninguna variable global del servidor MySQL.

El worker rechaza explícitamente `root`, `jesus_admin` y `kp_data_manager_app`. El usuario ETL debe crearse posteriormente con permisos mínimos:

- `SELECT`, `UPDATE` sobre `kp_control.import_batch`.
- `INSERT` sobre `kp_control.import_error`.
- `INSERT` sobre `kp_bronze.raw_pagos`.
- `INSERT`, `SELECT` sobre `kp_bronze.raw_cartera_bbva` para correlacionar `source_row` con `raw_id` dentro del chunk.
- `INSERT`, `SELECT` sobre `kp_bronze.raw_cartera_caja_arequipa` para la misma correlación por chunk.
- `INSERT`, `SELECT` sobre `kp_bronze.raw_cartera_compartamos` para la misma correlación por chunk.
- `INSERT`, `SELECT` sobre `kp_bronze.raw_cartera_confianza` para la misma correlación por chunk.
- `INSERT`, `SELECT` sobre `kp_bronze.raw_cartera_wandoo` para la misma correlación por chunk.
- `INSERT`, `SELECT` sobre `kp_silver.cartera_operaciones`.
- `INSERT` sobre `kp_silver.cartera_contactos` y `kp_silver.cartera_direcciones`.
- `INSERT` sobre `kp_silver.cartera_caja_arequipa_detalle`, `kp_silver.cartera_avales` y `kp_silver.cartera_garantias`.
- `INSERT` sobre `kp_silver.cartera_compartamos_detalle`.
- `INSERT` sobre `kp_silver.cartera_confianza_detalle`.
- `INSERT` sobre `kp_silver.cartera_wandoo_detalle`.

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
14. `database/sql/017_create_raw_cartera_compartamos.sql`.
15. `database/sql/018_create_cartera_compartamos_detalle.sql`.
16. `database/sql/020_create_raw_cartera_confianza.sql`.
17. `database/sql/021_create_cartera_confianza_detalle.sql`.
18. `database/sql/022_create_raw_cartera_wandoo.sql`.
19. `database/sql/023_create_cartera_wandoo_detalle.sql`.

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
DB_QUEUE_RETRY_AFTER=3720
IMPORT_ENFORCE_ETL_FILE_ACCESS=true
IMPORT_ETL_USER=kpdeploy
IMPORT_SHARED_GROUP=kpdm-imports
IMPORT_FILE_MODE=0640
IMPORT_DIRECTORY_MODE=2750
```

En Linux, `kpdmweb` y `kpdeploy` deben pertenecer a un grupo compartido dedicado
(`kpdm-imports`). El directorio `storage/app/private/imports` debe pertenecer a ese
grupo, conservar el bit setgid y tener ACL por defecto para lectura/traversal del
grupo. El servicio aplica y verifica grupo y modos antes de dejar un batch listo y
vuelve a comprobar el acceso antes de encolarlo. Los archivos permanecen privados:
`0640` para archivos y `2750` para directorios; nunca se requiere `0777`.

En Linux, `ETL_PYTHON_BINARY` puede apuntar al Python aislado, por ejemplo `/opt/kp-data-etl/.venv/bin/python`.

Iniciar el worker local desde la raíz Laravel:

```bash
php artisan queue:work --queue=etl
```

`DB_QUEUE_RETRY_AFTER` debe superar el timeout máximo del Job para impedir una segunda reserva mientras el proceso sigue activo. `ETL_PROCESS_TIMEOUT_SECONDS=0` desactiva el timeout del proceso, pero exige configurar `DB_QUEUE_RETRY_AFTER` por encima de la duración máxima operacional esperada.

## Flujo del batch

1. Lee la carga y exige estado `PENDIENTE`.
2. Resuelve el loader con un registry: `PAGOS` conserva su loader; Carteras admite los perfiles registrados BBVA v1, Caja Arequipa v1, Compartamos v1, Financiera Confianza v1 y Wandoo v1. Cualquier combinación no registrada se rechaza.
3. Resuelve `archivo_ruta` dentro de `ETL_IMPORT_STORAGE_ROOT`, sin permitir rutas absolutas, `..` ni symlinks externos.
4. Verifica existencia, extensión y SHA-256 contra los metadatos registrados.
5. Reclama la carga atómicamente como `PROCESANDO` y reinicia sus contadores.
6. Lee CSV o XLSX como iterador.
7. Normaliza y valida cada fila.
8. Inserta por `executemany` en transacciones cortas de aproximadamente `ETL_INSERT_BATCH_SIZE` filas.
9. Actualiza contadores periódicamente.
10. Finaliza como `COMPLETADO`, `COMPLETADO_CON_ERRORES` o `ERROR`, siempre con fechas UTC.

### Carteras: BBVA v1, Caja Arequipa v1, Compartamos v1, Financiera Confianza v1 y Wandoo v1

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

Caja Arequipa v1 exige 66 posiciones exactas, termina en `COSECHA` y conserva por separado las dos columnas fuente llamadas `NRO_DOC_TIT`. Su documento efectivo requiere coincidencia o usa la única ocurrencia informada. Como la fuente no incluye un identificador adicional, `cartera_operaciones.identificador_origen` queda `NULL`. Las fechas numéricas se convierten con el epoch del workbook, los teléfonos `TEL_TIT` y `TEL_GES` se extraen desde celdas con uno o varios valores, y los datos específicos se distribuyen entre detalle, avales y hasta seis garantías. Todas las escrituras de una fila válida permanecen dentro de la transacción corta del chunk.

Compartamos v1 valida exactamente 30 posiciones en su orden canónico, permitiendo solo whitespace exterior (incluido NBSP) en los encabezados. `NumDoc`, `Ctacliente` y `Operación` se preservan como texto; `identificador_origen` queda `NULL`. Sus atributos auxiliares reales se guardan en `cartera_compartamos_detalle`, incluyendo `TipCambio` como `DECIMAL(18,6)`. `FecDesembolso` admite dos representaciones: un año aislado (`1900..2100`) deja `cartera_operaciones.fecha_desembolso` en `NULL`, mientras una fecha completa se conserva allí como `DATE`; en ambos casos el año disponible se guarda en `cartera_compartamos_detalle.anio_desembolso`. Bronze conserva siempre el valor fuente. Las direcciones se registran como `CLIENTE` y `NEGOCIO` cuando tienen contenido.

Financiera Confianza v1 valida exactamente 27 posiciones. `DNI`, `Cuenta Cliente` y `Operacion` se conservan como texto para no perder ceros iniciales. La moneda origen `0` se proyecta como `PEN` y `101` como `USD`; otros códigos quedan sin moneda canónica. PEN selecciona `Saldo Capital MN` y USD selecciona `Saldo Capital MO`, sin sumar ambos ni ejecutar conversiones. `deuda_total` suma exclusivamente ese capital canónico y los componentes financieros preservados en `cartera_confianza_detalle`. `Interés Compensatorio` alimenta `interes` e `Interés Moratorio` alimenta `mora`. `Fecha Castigo` admite fechas explícitas, valores nativos y seriales Excel usando el epoch del workbook.

Wandoo v1 valida exactamente 19 posiciones y conserva sus headers Unicode como contrato de entrada, mientras Bronze usa nombres físicos ASCII `snake_case`. `DNI` y `Numero de Prestamo` se mantienen como identificadores textuales; el préstamo alimenta únicamente `operacion`. Como `cartera_operaciones.cuenta` es obligatorio, se reutiliza el contrato documentado que deriva la cuenta anteponiendo exactamente un `0` al DNI, sin aplicar `LPAD`. `Saldo deudor` alimenta tanto `saldo_capital` como `deuda_total` con el mismo `Decimal`, sin sumas ni fórmulas adicionales; moneda, interés y mora permanecen `NULL`. `Días de mora` se conserva como cantidad de días y no como importe. La fuente no contiene teléfonos, por lo que una carga válida genera cero contactos.

`Fecha Últ. Pago` y `Fecha otorgamiento crédito` aceptan fechas explícitas, valores nativos y seriales Excel usando el epoch del workbook. La fecha de otorgamiento también alimenta `fecha_desembolso`. La geografía se proyecta a la operación y a una dirección `CLIENTE` con calle `NULL`, que el esquema común permite. El producto crediticio se proyecta a `producto`; todos los atributos específicos permanecen trazables en `cartera_wandoo_detalle`. No se infiere moneda a partir de `Total soles pagados`.

Los cuatro perfiles comparten `normalize_phone`: conserva únicamente celulares peruanos `9XXXXXXXX`, acepta opcionalmente el prefijo `51` y lo elimina, y descarta fijos, longitudes no canónicas y valores repetitivos. `extract_phones` separa celdas multivalor por `|`, `/`, `;`, CR o LF sin romper celulares formateados con espacios o guiones. La deduplicación ocurre después de normalizar y solo dentro de una misma operación. Caja Arequipa elimina whitespace de `COSECHA` solo al construir Silver; Bronze conserva el valor fuente.

### SEARCH PERSONAS v1

El loader SEARCH es independiente de Pagos y Carteras. PERSONAS v1 recibe un mapping versionado, conserva todas las posiciones fuente en `kp_bronze.search_raw_row`, acepta únicamente DNI ASCII de ocho dígitos y persiste Silver histórico por batch en `kp_silver.search_personas`. Dos filas del mismo batch con igual DNI son ambiguas: la segunda se registra como error, la barrera `UNIQUE (batch_id, documento)` evita una aceptación accidental y el batch completo queda sin publicación Gold.

`row_hash` se calcula sobre el UTF-8 de un JSON canónico compacto, sin ordenar claves porque la estructura se construye en orden fijo: `{"version":1,"fields":[...]}`. Cada elemento incluye `position` (uno-based), `name` y `cell`; `cell` contiene un `type` explícito (`null`, `string`, `integer`, `decimal`, `date`, `datetime`, `time` o `boolean`) y `value`. Así `NULL`, cadena vacía, cero y texto `"0"` son distintos. La huella es `SHA-256` hexadecimal de ese JSON previo a la normalización Silver.

`record_hash` usa el mismo JSON compacto y una lista fija de campos normalizados: `documento`, `paterno`, `materno`, `nombres`, `nombre_completo`, `fecha_nacimiento`, `direccion_origen`, `sexo`, `estado_civil`, `padre`, `madre`. Cada elemento incluye posición, nombre, tipo y valor; fechas usan ISO `YYYY-MM-DD` y `NULL` permanece tipado. La huella es el SHA-256 hexadecimal del UTF-8 resultante. Las pruebas comprueban determinismo y la distinción entre `NULL` y vacío en Raw.

Una carga con filas inválidas conserva Bronze y las filas Silver válidas como histórico, pero no publica. Una carga completamente válida publica en una transacción InnoDB multi-schema. `SCOPE_REPLACE` reemplaza únicamente documentos de `import_scope_document`; `FULL_REPLACE` hace upsert de la población validada y elimina filas Gold obsoletas por `batch_id` dentro de la misma transacción. El publicador verifica la igualdad exacta Silver/scope, bloquea el batch y rechaza cualquier segunda fuente PERSONAS mientras no exista una política formal de precedencia.

### SEARCH TELEFONOS v1

TELEFONOS reutiliza el mismo parser, Bronze genérico, loader, scope y publicador SEARCH. El contrato fuente contiene exactamente `DOCUMENTO`, `TELEFONO`, `OPERADOR` y `FECHA DATA`. `DOCUMENTO` acepta DNI ASCII de ocho dígitos; `TELEFONO` acepta únicamente `9XXXXXXXX`, rechaza valores repetitivos y bloquea explícitamente `900000000` y `911111111`. `FECHA DATA` es obligatoria y admite fecha XLSX tipada o texto ISO `YYYY-MM-DD`.

`operador_raw` conserva el texto funcional con trim y whitespace colapsado. `operador` se detecta en cualquier posición, sin distinguir mayúsculas y respetando límites de palabra, desde la lista cerrada compartida en `resources/contracts/search-telefonos-v1.json`. Los operadores se ordenan por longitud descendente para que `FLASH MOBILE` y `GUINEA MOBILE` prevalezcan sobre sus nombres cortos. Una fila sin coincidencias queda como `OPERATOR_INVALID`; dos operadores distintos producen `OPERATOR_AMBIGUOUS`.

El `row_hash` mantiene el algoritmo canónico común sobre las cuatro celdas fuente previas a Silver. El `record_hash` usa, en orden, `documento`, `telefono`, `operador_raw`, `operador` y `fecha_data`, con tipo explícito y fecha ISO. Dos filas con el mismo par documento/teléfono dentro del batch producen `DUPLICATE_DOCUMENT_PHONE` y bloquean la publicación; un documento puede tener varios teléfonos y el mismo teléfono puede pertenecer a documentos distintos.

`SCOPE_REPLACE` elimina en Gold exclusivamente los teléfonos de los documentos del scope oficial y luego inserta el conjunto Silver completo de esos documentos. `FULL_REPLACE` hace upsert set-based del batch y elimina las filas de batches anteriores. Ambas variantes se ejecutan en una sola transacción InnoDB multi-schema; Bronze y Silver nunca se eliminan. DM-F3 permite una sola fuente activa TELEFONOS hasta definir una política formal de fusión.

`UPSERT` está restringido en código y catálogo a `TELEFONOS / BASE_TELEFONOS`. Hace
un único `INSERT ... SELECT ... ON DUPLICATE KEY UPDATE` sobre la clave primaria
`(documento, telefono)`: inserta pares nuevos y actualiza operador, fecha y metadatos
del par existente. No ejecuta ningún `DELETE`, por lo que conserva teléfonos ausentes
del archivo y documentos ajenos al lote. La habilitación de `allows_upsert` es un
paso SQL manual posterior a las pruebas; no se activa automáticamente al desplegar.

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
