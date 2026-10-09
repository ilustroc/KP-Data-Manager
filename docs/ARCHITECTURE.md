# KP Data Manager — Arquitectura y plan de implementación

## 1. Estado del repositorio y alcance de este documento

Fecha de inspección: 2026-10-03.

La primera inspección encontró el directorio vacío y sin repositorio Git. El 2026-10-03 se incorporó `docs/database-schema.sql`, un snapshot sin datos del DDL real de MySQL 5.7.33, y se completó la Fase 1 sobre Laravel 13.34.0 con PHP objetivo 8.3.35. No se ejecutó ninguna sentencia contra bases productivas.

Este documento combina el esquema confirmado por el snapshot con la arquitectura propuesta. El snapshot permite confirmar estructura, pero no sustituye la inspección de datos, conteos, cardinalidad ni planes `EXPLAIN` en el servidor. Todo SQL correctivo se conserva versionado en `database/sql/` y requiere revisión y ejecución manual.

### Alcance inicial

- Importación histórica y diaria de pagos desde CSV/XLSX.
- Consulta server-side de pagos actuales y pagos sin identificar.
- Identificación/corrección del documento efectivo sin modificar Bronze.
- Auditoría íntegra de las resoluciones.
- Control, progreso, historial y errores de importaciones.
- Autenticación y roles `ADMIN`, `OPERADOR` y `LECTURA`.

Quedan fuera por ahora: gestiones, asignaciones, CNA, clientes, audios, PDP, Gold completo y Power BI. La solución se divide por dominio para que estas fuentes puedan incorporarse después sin convertir el módulo de pagos en el núcleo monolítico de la aplicación.

## 2. Restricciones y principios obligatorios

1. `kp_bronze` es inmutable desde la aplicación. El único alta permitida en `raw_pagos` es la ingestión; nunca se actualizan sus valores de negocio.
2. `DOCUMENTO` y `OPERACION` se tratan como texto de extremo a extremo. No se convierten a tipos numéricos y se conservan sus ceros iniciales.
3. `MONTO` y `ACUMULADO` usan `Decimal` en Python y `DECIMAL` en MySQL; nunca `float`.
4. Las consultas y scripts deben ser compatibles con MySQL Community 5.7.33: sin CTE, window functions, `JSON_TABLE`, índices parciales ni dependencias de `CHECK` moderno.
5. Los archivos grandes no se procesan en una request HTTP ni se cargan completos en memoria.
6. Los inserts se realizan por lotes y la detección de duplicados no hace una consulta por fila.
7. Los archivos se almacenan fuera de `public` y no tienen URL directa.
8. Toda mutación se valida y autoriza en backend; el usuario de auditoría se obtiene de la sesión autenticada.
9. Laravel y el worker usan cuentas MySQL propias con privilegio mínimo. No usan `root`, `jesus_admin` ni alteran `kpinvest_db`.
10. Cada fase tiene una puerta de calidad: no se inicia la siguiente mientras fallen pruebas importantes de la fase actual.

## 3. Arquitectura lógica

```text
Navegador
   |
   | HTTPS, CSRF, sesión, autorización
   v
Nginx -> PHP-FPM 8.3 (/run/php/php83-kpinvest.sock)
   |
   v
Laravel (UI + API interna + servicios de aplicación)
   |                    |
   |                    +--> storage/app/private/imports (sin acceso web)
   |
   +--> kp_silver  : consultas efectivas
   +--> kp_control : batches, errores, resoluciones y auditoría
   +--> kp_bronze  : lectura + inserción ETL; sin UPDATE/DELETE de negocio
   +--> kp_gold    : reservado para indicadores posteriores

Proceso independiente supervisado
   |
   v
Python ETL (.venv) -> streaming CSV/XLSX -> normalización -> lotes MySQL
                                      \-> progreso/errores en kp_control
```

### Responsabilidades

**Laravel**

- Autenticación, sesiones, roles y políticas.
- Renderizado del sistema administrativo.
- Filtros, paginación SQL y vistas de detalle/auditoría.
- Recepción segura del archivo y cálculo de SHA-256 en streaming.
- Creación de la carga en `kp_control.import_batch`.
- Resolución transaccional de documentos.
- Endpoints de polling y descarga CSV de errores.
- Orquestación del worker sin ejecutar ETL pesado en el request.

**Python ETL**

- Reclamo seguro de batches pendientes.
- Lectura streaming de CSV y XLSX.
- Validación de encabezados, normalización y validación por fila.
- Huella técnica SHA-256 e inserts masivos sin deduplicación automática de pagos.
- Registro agrupado de errores y actualización periódica de progreso.
- Logging estructurado sin secretos.

**MySQL**

- Persistencia RAW inmutable, resoluciones y control de cargas.
- Vistas Silver para el valor efectivo.
- Índices para filtros y joins.
- Transacciones e integridad referencial donde el estado real del esquema lo permita.

## 4. Organización propuesta

```text
KP-Data-Manager/
├── app/
│   ├── Console/Commands/
│   ├── Domain/
│   │   ├── Imports/
│   │   └── Payments/
│   ├── Http/
│   │   ├── Controllers/
│   │   ├── Middleware/
│   │   └── Requests/
│   ├── Models/
│   ├── Policies/
│   ├── Services/
│   │   ├── Imports/
│   │   └── Payments/
│   └── Support/
├── config/
├── database/
│   ├── migrations/
│   └── sql/
│       ├── preflight/
│       ├── views/
│       └── indexes/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── RUNBOOK.md
├── etl/
│   ├── .venv/                 # local/servidor, ignorado por Git
│   ├── requirements.txt
│   ├── src/
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── logging_config.py
│   │   ├── worker.py
│   │   ├── loaders/
│   │   │   ├── base_loader.py
│   │   │   └── pagos_loader.py
│   │   └── parsers/
│   │       ├── csv_parser.py
│   │       └── xlsx_parser.py
│   └── tests/
├── resources/
│   ├── css/
│   ├── js/
│   └── views/
│       ├── components/
│       ├── dashboard/
│       ├── imports/
│       ├── layouts/
│       └── payments/
├── routes/
├── storage/app/private/imports/  # ignorado por Git
└── tests/
    ├── Feature/
    └── Unit/
```

`Domain` contendrá enums/objetos de valor y contratos estables; `Services` coordinará casos de uso. Solo se añadirá una capa `Repositories` si aparecen implementaciones intercambiables o consultas complejas que no encajen en servicios/query objects. Se evita crear abstracciones vacías.

La interfaz se construirá con Blade y componentes reutilizables, salvo que en la Fase 1 aparezca una necesidad real de SPA. Para este sistema administrativo, filtros server-side y polling, Blade reduce complejidad operativa y superficie de ataque.

La Fase 1 confirma Blade + Tailwind CSS 4 como stack de interfaz. Laravel 13 es compatible con PHP 8.3 y su soporte de base de datos incluye MySQL 5.7+. `composer.json` fija la plataforma PHP en 8.3.35 para evitar resolver dependencias incompatibles con producción.

## 5. Conexiones y acceso a datos

Las credenciales se suministran exclusivamente por `.env`; `.env.example` contiene nombres, nunca secretos. Se configurarán conexiones nombradas:

- `mysql_bronze`
- `mysql_silver`
- `mysql_control`
- `mysql_gold`

Pueden compartir host, puerto y usuario si la política de privilegios lo admite, pero cada modelo declara explícitamente conexión y tabla. Cuando una consulta necesite cruzar esquemas del mismo servidor, se usará una conexión principal con nombres calificados y parámetros enlazados. No se construyen nombres de esquema a partir de input del usuario.

`mysql_control` es la conexión predeterminada de Laravel: allí se alojarán usuarios, sesiones, cache, jobs y tablas de control. Los tests usan SQLite en memoria únicamente para la Fase 1; las pruebas de integración del SQL heredado deberán ejecutarse contra MySQL 5.7. Las variables de esquema son `DB_BRONZE_DATABASE`, `DB_SILVER_DATABASE`, `DB_CONTROL_DATABASE` y `DB_GOLD_DATABASE`, compartiendo host y una cuenta de aplicación no privilegiada.

Privilegios esperados, sujetos a validación con infraestructura:

- Laravel: `SELECT` en Bronze/Silver; `SELECT/INSERT/UPDATE` únicamente en objetos necesarios de Control; acceso a tablas propias de autenticación; sin `DROP`, `ALTER` ni `GRANT` en runtime.
- Worker: `SELECT/INSERT` en objetos de ingestión Bronze; `SELECT/INSERT/UPDATE` en batches y errores de Control; sin `UPDATE/DELETE` sobre filas RAW.
- Migraciones/despliegue: cuenta separada y temporal con DDL limitado a los esquemas aprobados.

## 6. Objetos de datos

### Estructura física confirmada por `docs/database-schema.sql`

**`kp_bronze.raw_pagos`** usa InnoDB/utf8mb4. Conserva exactamente en primer lugar `FECHA DATE`, `DOCUMENTO VARCHAR(30)`, `MONTO DECIMAL(15,2)`, `ACUMULADO DECIMAL(15,2)`, `RECAUDO VARCHAR(50)`, `OPERACION VARCHAR(100)`, `COMENTARIO VARCHAR(260)` y `HORA TIME`, todos nullable. Después contiene `raw_id BIGINT UNSIGNED AUTO_INCREMENT`, `source_file VARCHAR(255)`, `batch_id VARCHAR(100)` e `ingested_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP`. Su única clave/índice actual es `PRIMARY KEY(raw_id)`. No existe todavía `row_hash` ni índices para los filtros previstos.

**`kp_control.pago_documento_resolucion`** usa InnoDB/utf8mb4. Contiene `id_resolucion BIGINT UNSIGNED AUTO_INCREMENT` como PK; `raw_pago_id BIGINT UNSIGNED NOT NULL`; documentos anterior nullable y nuevo obligatorio en `VARCHAR(30)`; `motivo VARCHAR(260)` nullable; `usuario VARCHAR(100) NOT NULL`; `fecha_modificacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP`; y `activo TINYINT(1) NOT NULL DEFAULT 1`. Tiene índices individuales por `raw_pago_id`, `documento_nuevo` y `fecha_modificacion`. No tiene FK, índice compuesto `(raw_pago_id, activo)` ni restricción física que impida dos resoluciones activas.

**`kp_control.import_batch`** usa InnoDB/utf8mb4. Su PK es `batch_id BIGINT UNSIGNED AUTO_INCREMENT`; contiene `tipo`, `origen`, `archivo`, fechas, estado, cuatro contadores unsigned, usuario y mensaje de error. Tiene índices individuales por `tipo`, `estado` y `fecha_inicio`. `fecha_inicio` es obligatorio. No conserva todavía nombre original e interno por separado, tamaño ni SHA-256.

El snapshot conserva una diferencia histórica: `import_batch.batch_id` es `BIGINT UNSIGNED`, mientras `raw_pagos.batch_id` todavía es `VARCHAR(100)`. Como los valores históricos verificados son `NULL`, `007_align_raw_pagos_batch_id.sql` propone convertir la columna Bronze a `BIGINT UNSIGNED NULL` y agregar un índice no único. No se crea foreign key entre esquemas.

**`kp_silver.v_pagos_actuales`** expone 13 columnas, incluida `DOCUMENTO_ORIGINAL`, y calcula `DOCUMENTO` con `COALESCE(R.documento_nuevo, P.DOCUMENTO)`. Hace `LEFT JOIN` contra resoluciones con `activo = 1`. Es correcta funcionalmente si existe como máximo una resolución activa; con dos activas devolvería dos filas para el mismo pago.

**`kp_silver.v_pagos_sin_identificar`** proyecta las mismas 13 columnas desde `v_pagos_actuales` y filtra correctamente `DOCUMENTO IS NULL OR TRIM(DOCUMENTO) = ''`.

Ambas vistas son `SQL SECURITY DEFINER` y dependen de `DEFINER=jesus_admin@127.0.0.1`. Laravel no usará ese usuario, pero la dependencia del definer es un riesgo operativo y de privilegios. El script pendiente `005_recreate_pago_views_as_invoker.sql` conserva la semántica y cambia las vistas a `SQL SECURITY INVOKER`; antes de aplicarlo se deben otorgar al usuario de aplicación los `SELECT` mínimos sobre los objetos subyacentes.

### Objeto nuevo requerido

`kp_control.import_error`:

| Campo | Tipo requerido |
|---|---|
| `id` | `BIGINT UNSIGNED` autoincremental, PK |
| `batch_id` | `BIGINT UNSIGNED`, FK a `import_batch.batch_id` |
| `numero_fila` | `BIGINT UNSIGNED` |
| `campo` | `VARCHAR(100)` |
| `valor` | `TEXT` |
| `error` | `VARCHAR(500)` |
| `created_at` | `DATETIME` |

El snapshot confirma que ambos lados de la FK pueden usar `BIGINT UNSIGNED` e InnoDB. El script `001_create_import_error.sql` propone FK restrictiva, índice compuesto `(batch_id, numero_fila)` y un índice por `numero_fila`.

### DDL versionado pendiente

Ninguno de estos scripts fue ejecutado:

1. `001_create_import_error.sql`: crea el registro de errores y su FK.
2. `002_extend_import_batch_file_metadata.sql`: agrega nombre original/interno, tamaño y SHA-256 único nullable.
3. `003_add_raw_pagos_row_hash.sql`: agrega `row_hash` nullable e índice no único; no presupone que el histórico sea único.
4. `004_add_pago_resolucion_lookup_index.sql`: agrega `(raw_pago_id, activo)` para el join y la transacción de resolución.
5. `005_recreate_pago_views_as_invoker.sql`: elimina la dependencia de seguridad de `jesus_admin` sin cambiar columnas o lógica.

### Inspección obligatoria antes del primer DDL

Guardar evidencia en `database/sql/preflight/` o en el registro de despliegue:

```sql
SELECT VERSION();
SHOW CREATE TABLE kp_bronze.raw_pagos;
SHOW INDEX FROM kp_bronze.raw_pagos;
SHOW CREATE TABLE kp_control.pago_documento_resolucion;
SHOW INDEX FROM kp_control.pago_documento_resolucion;
SHOW CREATE TABLE kp_control.import_batch;
SHOW INDEX FROM kp_control.import_batch;
SHOW CREATE VIEW kp_silver.v_pagos_actuales;
SHOW CREATE VIEW kp_silver.v_pagos_sin_identificar;
```

El snapshot ya confirmó columnas, claves, índices, engine, charset y definiciones de vistas. Todavía se deben revisar en el servidor conteos, nulos, resoluciones activas duplicadas, hashes potenciales, tamaños y planes `EXPLAIN`. No se ejecutará DDL sobre `raw_pagos` ni se reemplazarán vistas hasta completar esa revisión y preparar rollback.

## 7. Consulta de pagos

`PaymentQueryService` centralizará filtros autorizados y paginación. La UI nunca recibirá el dataset completo.

- Fuente de “Todos”: `kp_silver.v_pagos_actuales`.
- Fuente de “Sin identificar”: `kp_silver.v_pagos_sin_identificar`.
- Tamaños permitidos: 25, 50 o 100; cualquier otro valor se rechaza o normaliza a 25.
- Orden predeterminado estable: fecha descendente y `raw_id` descendente.
- Filtros: rango de fecha, documento, operación, recaudo, rango de monto y estado.
- Los nombres de columnas y dirección de orden pertenecen a una allowlist; los valores usan bindings.
- Búsquedas de documento/operación deben favorecer coincidencia exacta o prefijo. Un comodín inicial sobre millones de filas se reservará para una búsqueda explícita y evaluada.
- El total de la paginación puede ser costoso; se medirá `paginate()` frente a `simplePaginate()`/cursor pagination. La UX decidirá si necesita el conteo exacto en cada consulta.

La lista muestra solo `DOCUMENTO`, que siempre significa documento efectivo. `DOCUMENTO` original aparece únicamente en historial/auditoría.

### Índices candidatos, no autorizados hasta medir

- `raw_pagos(FECHA, raw_id)`.
- `raw_pagos(DOCUMENTO)`.
- `raw_pagos(OPERACION)`.
- `raw_pagos(RECAUDO)` si su selectividad lo justifica.
- `raw_pagos(row_hash)` tras sanear el histórico.
- `pago_documento_resolucion(raw_pago_id, activo)`.
- `pago_documento_resolucion(raw_pago_id, fecha_modificacion)`.

MySQL puede no materializar/optimizar una vista como se espera. Cada consulta principal se validará con `EXPLAIN` contra datos representativos antes de agregar índices.

## 8. Flujo de resolución de DOCUMENTO

Entrada: `raw_id`, `documento_nuevo`, `motivo`; el usuario no se recibe del navegador.

1. Autorizar al usuario (`ADMIN` u `OPERADOR`).
2. Validar `DOCUMENTO`: requerido, string, `trim`, longitud máxima 30. No aplicarle reglas numéricas.
3. Validar `MOTIVO`: string opcional/requerido según decisión de negocio, máximo 260. Se recomienda requerido para toda corrección auditable.
4. Iniciar transacción en la conexión que permita acceder a Bronze y Control.
5. Bloquear la fila `kp_bronze.raw_pagos` con `SELECT ... FOR UPDATE`. Este bloqueo serializa correcciones concurrentes del mismo `raw_id` sin requerir índices parciales, que MySQL 5.7 no soporta.
6. Buscar la resolución activa por `raw_pago_id` dentro de la misma transacción y bloquearla si existe.
7. Calcular el documento efectivo anterior con la resolución activa o, en su ausencia, el `DOCUMENTO` RAW.
8. Si el nuevo valor es igual al efectivo anterior, rechazar el no-op con un mensaje claro; no generar ruido de auditoría.
9. Desactivar la resolución vigente, si existe.
10. Insertar una nueva resolución activa con valores anterior/nuevo, motivo, identidad autenticada y fecha del servidor/base de datos.
11. Confirmar la transacción. Ante cualquier error, rollback completo.

```text
raw_pagos.DOCUMENTO (inmutable)
          |
          +-- sin resolución activa --> DOCUMENTO efectivo = valor RAW
          |
          +-- resolución activa ------> DOCUMENTO efectivo = documento_nuevo
```

La restricción “máximo una activa” se garantiza por servicio transaccional y bloqueo por pago. MySQL 5.7 no ofrece un índice único parcial sencillo sobre `activo = 1`. Antes de elegir una técnica adicional (por ejemplo columna generada nullable) se inspeccionarán datos y versión exacta; el servicio no dependerá de ella para ser correcto.

`PaymentResolutionService` será la única vía de escritura desde Laravel. No habrá endpoint para borrar historial. Las Policies impedirán modificaciones a `LECTURA`.

## 9. Flujo de importación

### 9.1 Recepción en Laravel

1. Autorizar `ADMIN`/`OPERADOR`.
2. Validar límite configurable, extensión permitida (`csv`, `xlsx`) y firma/contenido real; no confiar en MIME del navegador.
3. Generar nombre interno aleatorio y guardar mediante streaming en `storage/app/private/imports/`.
4. Calcular SHA-256 del archivo mediante streaming.
5. Registrar nombre original saneado, nombre interno, tamaño y hash. Esos campos no existen en el snapshot; están propuestos de forma nullable en `002_extend_import_batch_file_metadata.sql`.
6. Crear `import_batch` en estado `PENDIENTE` dentro de una operación consistente.
7. Responder inmediatamente; no abrir ni transformar el archivo en el request.

Los archivos nunca se sirven con `Storage::url`. Cualquier descarga futura pasará por un controller autorizado y con cabeceras seguras. La política de retención se definirá antes de producción; una limpieza automática nunca borrará archivos de batches en proceso.

### 9.2 Reclamo y ejecución del worker

En Fase 5 el worker se ejecuta manualmente con `python -m src.worker --batch-id X`; no existe scheduler, Supervisor, systemd ni invocación automática desde Laravel. El reclamo usa un `UPDATE` condicional y atómico de `PENDIENTE` a `PROCESANDO`, compatible con MySQL 5.7, para impedir que dos procesos reclamen el mismo batch.

1. Cambiar batch a `PROCESANDO` y fijar inicio.
2. Elegir parser por contenido/extensión validada.
3. Leer y normalizar encabezados.
4. Exigir `FECHA`, `MONTO` y `RECAUDO`. `DOCUMENTO`, `ACUMULADO`, `OPERACION`, `COMENTARIO` y `HORA` son opcionales y se representan como `NULL` cuando el encabezado falta. Se toleran espacios periféricos y diferencias de mayúsculas/minúsculas, no encabezados obligatorios ausentes ni encabezados ambiguos/duplicados.
5. Producir filas una a una, normalizarlas y acumular un chunk configurable (`ETL_INSERT_BATCH_SIZE`, default 5000).
6. Registrar errores de validación por fila sin truncar silenciosamente.
7. Calcular `row_hash` como huella técnica y ejecutar inserciones masivas por chunk sin deduplicar filas.
8. Actualizar contadores/progreso después de cada chunk confirmado, no por fila.
9. Finalizar en `COMPLETADO`, `COMPLETADO_CON_ERRORES` o `ERROR`, con fecha final y mensaje sanitizado.

Una caída conserva los chunks ya confirmados, marca el batch `ERROR` y no borra Bronze. Los contadores representan chunks confirmados. El reprocesamiento/rollback futuro podrá localizar filas mediante `batch_id`, pero Fase 5 no intenta ser idempotente por `row_hash` ni permite reprocesar automáticamente un batch terminal.

### 9.3 Parsing y memoria

- CSV: módulo estándar `csv`, archivo abierto como stream, encoding detectado/validado con una política explícita, límites razonables de campo y número físico de línea preservado.
- XLSX: `openpyxl.load_workbook(read_only=True, data_only=True)`, iteración `iter_rows()` y cierre garantizado del workbook. Se conservan metadatos mínimos de celda para interpretar máscaras inequívocas de ceros.
- Nunca `pandas.read_excel()` ni estructuras con el archivo completo.
- El uso de memoria debe ser aproximadamente proporcional a `IMPORT_BATCH_SIZE`, no al número total de filas.
- Las fórmulas XLSX se leen por su valor cacheado. Si falta valor cacheado, la fila genera un error explícito; el worker no evalúa fórmulas.

### 9.4 Normalización por fila

| Campo | Regla |
|---|---|
| `FECHA` | Aceptar objetos fecha de XLSX y formatos explícitos como `dd/mm/YYYY` e ISO `YYYY-mm-dd`; convertir a `date`; rechazar ambigüedad/no válido. |
| `DOCUMENTO` | Convertir de forma no destructiva a string, `trim`, vacío a `NULL`, máximo 30; conservar ceros iniciales cuando el origen sea textual. |
| `MONTO` | Limpiar `S/`, espacios y separador de miles admitido; parsear con `Decimal`; cuantizar/validar escala 2 y rango de `DECIMAL(15,2)`. |
| `ACUMULADO` | Igual a `MONTO`. |
| `RECAUDO` | String con `trim`, validar longitud contra DDL real. |
| `OPERACION` | String con `trim`, máximo según DDL; nunca entero; conservar ceros iniciales cuando el origen sea textual. |
| `COMENTARIO` | String, máximo 260; exceder el máximo genera `import_error`, nunca truncamiento. |
| `HORA` | Aceptar objeto time/datetime XLSX, `HH:MM` y `HH:MM:SS`; convertir a `time`; vacío permanece `NULL`. |

Una celda XLSX almacenada físicamente como número ya perdió su formato textual semántico al llegar al parser. No se inventarán ceros que no estén presentes, excepto cuando un formato Excel inequívoco pueda preservarse de forma probada; se documentará el error/advertencia para incentivar columnas de Documento/Operación como texto.

## 10. Estrategia de duplicados

### Hash lógico

`row_hash` es SHA-256 hexadecimal de una serialización canónica y versionada de los ocho valores Bronze normalizados:

- `FECHA`
- `DOCUMENTO`
- `MONTO`
- `ACUMULADO`
- `RECAUDO`
- `OPERACION`
- `COMENTARIO`
- `HORA`

La serialización debe evitar colisiones por concatenación: campos en orden fijo, representación canónica (`YYYY-MM-DD`, decimal con dos posiciones, `HH:MM:SS`), marcador explícito para `NULL` y longitudes/separadores escapados. La versión del algoritmo queda documentada y cubierta por vectores de prueba.

No se usa `OPERACION` como clave única. Dos filas con el mismo `row_hash` pueden ser pagos reales distintos: la huella sirve para análisis y auditoría futura, no como identidad de negocio.

### Implantación segura

1. Agregar `row_hash CHAR(64) NULL` sin índice único, después del preflight.
2. Calcular hashes históricos en lotes pequeños, con seguimiento y posibilidad de pausar.
3. Analizar grupos repetidos y confirmar la semántica con negocio. No borrar ni modificar filas históricas automáticamente.
4. Crear un índice no único para análisis; no convertirlo en `UNIQUE` ni usarlo para descartar filas.
5. Insertar todas las filas válidas con `executemany`/insert multi-row dentro de la transacción corta del chunk.

El SHA-256 del archivo evita registrar accidentalmente el mismo archivo exacto en Fase 4. `row_hash` no evita repeticiones entre archivos y `filas_duplicadas` permanece en cero durante Fase 5.

## 11. Batches, progreso y errores

La pantalla de detalle consulta un endpoint JSON autorizado cada pocos segundos. La respuesta incluye solo estado, contadores, fechas y mensaje seguro. El polling se detiene en estados terminales.

Estados:

- `PENDIENTE`
- `PROCESANDO`
- `COMPLETADO`
- `COMPLETADO_CON_ERRORES`
- `ERROR`

Invariantes sugeridas:

- `filas_insertadas + filas_duplicadas + filas_error` debe concordar con las filas de datos procesadas, considerando y documentando si el encabezado se excluye de `filas_archivo`.
- Los contadores solo avanzan después del commit del chunk correspondiente.
- Un error fatal conserva los contadores ya confirmados y un mensaje sanitizado; el detalle técnico queda en logs.

La descarga de errores usa una respuesta CSV en streaming por cursor/chunks, ordenada por `numero_fila, id`, para no cargar todos los errores en memoria.

## 12. UI y navegación

Sidebar inicial:

- Dashboard
- Cargas
  - Nueva carga
  - Historial
- Pagos
  - Todos
  - Sin identificar
  - Correcciones

Diseño desktop-first, responsive, sidebar oscuro y contenido claro. Sin gradientes ni animaciones innecesarias. Componentes reutilizables para filtros, paginación, tablas, badges, estados vacíos, mensajes de validación y paneles de detalle.

Rutas objetivo:

```text
GET  /dashboard
GET  /imports
GET  /imports/create
POST /imports
GET  /imports/{batch}
GET  /imports/{batch}/status
GET  /imports/{batch}/errors.csv

GET  /pagos
GET  /pagos/sin-identificar
GET  /pagos/{raw_id}
GET  /pagos/{raw_id}/historial
POST /pagos/{raw_id}/identificar
```

La misma acción de dominio sirve para identificación inicial y corrección. Si se necesita semántica REST más explícita, el endpoint podrá ser `POST /pagos/{raw_id}/resoluciones`; las URLs finales se fijarán en la fase correspondiente.

El dashboard consultará agregados indexables y acotados. Antes de ejecutar sumas completas frecuentes sobre millones de filas se medirán planes y tiempos; si son costosos, se añadirá una tabla de resumen actualizada por batch en una fase aprobada, no cache inconsistente en la UI. El gráfico por fecha será opcional y tendrá rango predeterminado acotado.

## 13. Seguridad

- Autenticación Laravel con hashes de contraseña provistos por el framework; nunca texto plano.
- Regeneración de sesión al iniciar sesión, cookies `HttpOnly`, `Secure` en HTTPS y `SameSite` apropiado.
- CSRF en todas las mutaciones web.
- Middleware de autenticación y Policies/Gates por capacidad, no solo ocultamiento visual.
- `ADMIN`: administración, cargas, resoluciones y lectura.
- `OPERADOR`: cargas, identificación/corrección, historial y lectura.
- `LECTURA`: consultas e historial, sin mutaciones.
- Validación mediante Form Requests y normalización controlada antes del servicio.
- Query Builder/Eloquent con parámetros; allowlist para columnas de orden.
- Identidad de auditoría tomada de `Auth::user()`. Se evaluará almacenar `user_id` además del texto histórico si la tabla actual lo permite.
- Escape por defecto en Blade; no renderizar comentarios/motivos como HTML.
- Rate limiting razonable para login y endpoints de polling/mutación.
- Protección contra path traversal: los nombres internos los genera el servidor y se resuelven dentro del disco privado.
- Logs sin credenciales, cookies, contenido completo de archivos ni información sensible innecesaria.
- Nginx solo apunta a `public/`; deniega dotfiles y limita tamaño de request coherentemente con la configuración Laravel/PHP.

Ubuntu 16.04 está fuera de soporte general y representa un riesgo de plataforma. No se tocará el stack legacy, pero antes de producción se debe registrar el riesgo, verificar parches compensatorios y aislar el nuevo virtual host/proceso. La modernización del sistema operativo debe planificarse por separado.

## 14. Observabilidad y operación

Laravel registra eventos de autenticación relevantes, creación de batches y fallos de servicios sin secretos. Python emite logs estructurados con:

- `batch_id`
- archivo/nombre interno seguro
- inicio y fin
- filas procesadas, insertadas, duplicadas y erróneas
- duración
- estado final
- excepción sanitizada y stack trace solo en el log técnico

El worker tendrá salida a archivos rotados/journald y será reiniciado por el supervisor con backoff. Se documentarán comandos de health check, reintento, conciliación de batches atascados, retención de archivos y rollback en `docs/RUNBOOK.md`.

## 15. Estrategia de pruebas

### Laravel

- Feature tests de autorización por rol.
- Tests de consulta de pagos contra fixtures con documento nulo, vacío, original y resuelto.
- Tests transaccionales del servicio de resolución y de conservación del historial.
- Test que compara todos los campos RAW antes/después de una resolución.
- Tests de filtros, límites de paginación y allowlist de orden.
- Tests de upload, almacenamiento privado, validación y polling.
- Test de descarga CSV por streaming.

Las pruebas no deben depender de características de SQLite que difieran de MySQL. Los tests de integración relevantes correrán contra MySQL 5.7 o un entorno compatible aprobado.

### Python

- Parsers CSV/XLSX con iteradores y archivos generados de prueba.
- Encabezados normalizados, ausentes, extra/ambiguos y duplicados.
- Comentario >260 produce error de fila.
- Documento y operación conservan ceros iniciales.
- Conversión exacta de fechas, horas y `Decimal`.
- Procesamiento multi-chunk con tamaño pequeño de prueba para demostrar streaming.
- Hash canónico estable, duplicado intra-chunk e inter-batch.
- Fallo/reintento sin doble inserción.

Además, se medirá memoria con un fixture grande generado incrementalmente; la prueba debe demostrar que no crece linealmente con el archivo.

## 16. Plan de implementación por fases

Cada fase empieza revisando el estado real del repositorio y termina con tests, análisis de errores y una decisión explícita de continuar. Los nombres pueden ajustarse al bootstrap real, pero no se ampliará el alcance funcional sin aprobación.

### FASE 1 — Bootstrap Laravel, DB, autenticación y layout

**Estado: implementada y validada localmente con PHP 8.3.35 (25 tests, 70 aserciones). Pendiente de despliegue y prueba de conexión con la cuenta MySQL de aplicación en el servidor.**

**Crear/modificar**

- Bootstrap Laravel 13.34.0 compatible con PHP 8.3, con dependencias fijadas en `composer.lock` y plataforma Composer 8.3.35.
- `.env.example`, `config/database.php` y configuración de discos privados.
- Modelos/conexiones base por esquema, sin DDL sobre tablas existentes.
- Autenticación, migraciones de usuarios/roles de la aplicación y Policies/Gates base.
- `resources/views/layouts/app.blade.php`, sidebar y componentes visuales.
- `routes/web.php`, dashboard inicial vacío/seguro.
- `.gitignore`, `README.md` y documentación de instalación.

**Validar antes**

- `/opt/php83/bin/php`, extensiones requeridas, `/usr/local/bin/composer83`, permisos del usuario de despliegue y compatibilidad de dependencias.
- Conectividad con una cuenta de aplicación no privilegiada.
- DDL real de los objetos existentes mediante las consultas de preflight.

**Tests/puerta**

- Suite del framework, login/logout, acceso anónimo, roles y conexión de solo lectura.
- No continuar si falla autenticación/autorización o si el bootstrap requiere alterar PHP 7/WordPress/configuración legacy.

### FASE 2 — Consultas de pagos, Todos y Sin identificar

**Crear/modificar**

- `app/Models/RawPayment.php` y modelos de lectura necesarios.
- `app/Services/Payments/PaymentQueryService.php`.
- `app/Http/Requests/Payments/PaymentIndexRequest.php`.
- `app/Http/Controllers/PaymentController.php`.
- Vistas `resources/views/payments/index.blade.php`, `unidentified.blade.php`, `show.blade.php` y componentes de filtros/tabla/paginación.
- Rutas GET del módulo.
- Scripts SQL de índices/vistas solo si la inspección demuestra que faltan o son incorrectos; revisión manual antes de aplicar.

**Tests/puerta**

- Pago sin documento efectivo aparece en sin identificar.
- Pago con documento RAW aparece identificado.
- Filtros, paginación 25/50/100 y columnas efectivas.
- `EXPLAIN` y benchmark con volumen representativo.
- No continuar si la consulta hace full scans inaceptables o expone documento original en la lista principal.

### FASE 3 — Identificación, corrección y auditoría

**Crear/modificar**

- `app/Models/PaymentDocumentResolution.php`.
- `app/Services/Payments/PaymentResolutionService.php`.
- `app/Http/Requests/Payments/StorePaymentResolutionRequest.php`.
- Controller/acciones y Policy de resolución.
- Formularios/modal de identificación/corrección e historial.
- Rutas POST y GET de historial.
- Índices de Control, únicamente después del preflight.

**Tests/puerta**

- Primera resolución asigna documento.
- Segunda resolución reemplaza el valor efectivo.
- Historial mantiene ambas, orden descendente.
- `raw_pagos` permanece byte/lógicamente igual.
- Rollback ante fallo entre desactivación e inserción.
- Correcciones concurrentes no dejan más de una activa.
- `LECTURA` recibe 403; usuario de browser no puede falsificar auditoría.
- No continuar si cualquier prueba de inmutabilidad, concurrencia o autorización falla.

### FASE 4 — `import_batch` y pantallas de cargas

**Crear/modificar**

- Migración/script revisado de `kp_control.import_error`.
- Ajustes mínimos y aprobados de `import_batch` para metadatos faltantes.
- `app/Models/ImportBatch.php`, `ImportError.php`.
- `app/Services/Imports/ImportBatchService.php` y servicio de almacenamiento.
- Form Request/controller de upload, historial, detalle, polling y CSV de errores.
- Vistas `imports/create`, `index`, `show` y badges de estado.
- Configuración de tamaño/retención y storage privado.

**Tests/puerta**

- Permisos por rol, tamaño/extensión/firma, nombre interno seguro y SHA-256.
- Archivo no accesible por URL pública.
- Transiciones/JSON de progreso y CSV grande en streaming.
- No continuar si el request procesa contenido ETL o si el archivo queda bajo `public`.

### FASE 5 — Python ETL, `.venv` y streaming CSV/XLSX

**Crear/modificar**

- `etl/requirements.txt` con versiones fijadas.
- `.venv` local/servidor creado con Python 3 e ignorado por Git.
- `etl/src/config.py`, `db.py`, `worker.py`, dominio, parsers y loaders.
- Parsers y loaders de la estructura propuesta.
- Tests pytest y fixtures pequeños/generadores.
- Script revisado para `row_hash` nullable con índice no único y script de alineación numérica de `batch_id`; ambos quedan pendientes de ejecución manual.

**Tests/puerta**

- Encabezados incorrectos fallan el batch.
- Comentario >260 genera `import_error` sin truncar.
- Operación/documento preservan ceros iniciales.
- CSV/XLSX se leen en streaming y un archivo grande atraviesa varios chunks.
- Inserción por lotes, conteos correctos y `filas_duplicadas = 0` sin descartar coincidencias de `row_hash`.
- Memoria acotada y compatibilidad MySQL 5.7.
- No continuar si se usa carga completa, insert por fila o aritmética `float`.

### FASE 6 — Integración Laravel ↔ worker Python

**Crear/modificar**

- Contrato final de estados, ownership y reintento de batches.
- Comando Laravel opcional de conciliación/diagnóstico, no de ETL pesado.
- Unidad `systemd` o configuración Supervisor aislada para el worker.
- Configuración Nginx/PHP-FPM del nuevo virtual host sin tocar servicios legacy.
- Endpoint de polling integrado y UX completa de progreso/error.
- `docs/DEPLOYMENT.md` y `docs/RUNBOOK.md`.

**Tests/puerta**

- Flujo E2E: upload → pendiente → procesando → estado terminal.
- Reinicio del worker a mitad de archivo sin duplicar datos confirmados.
- Dos workers/batches no reclaman el mismo trabajo.
- Fallos de archivo/DB producen estado y mensaje correctos.
- No continuar si se requieren permisos amplios o cambios en PHP 7, WordPress o `kpinvest_db`.

### FASE 7 — Tests, seguridad y optimización

**Crear/modificar**

- Completar suites Laravel/Python e integración.
- Hardening de Nginx, sesión, headers, rate limits, permisos y secretos.
- Índices ajustados por `EXPLAIN`/slow query log y benchmarks.
- Estrategia final de resumen del dashboard y gráfico acotado.
- Rotación de logs, retención de archivos y monitoreo de batches atascados.
- Checklist de despliegue, rollback, backup y aceptación.

**Tests/puerta de producción**

- Toda la matriz funcional solicitada en verde.
- Pruebas de concurrencia, volumen, memoria y reintento.
- Revisión de privilegios DB, exposición de archivos, CSRF, XSS, SQL injection y autorización.
- Prueba de restore/rollback documentada.
- No desplegar si queda una prueba crítica fallando; registrar cualquier excepción aceptada con dueño y fecha.

## 17. Decisiones pendientes que requieren evidencia

Estas decisiones no deben inventarse durante el desarrollo:

1. Volumen, distribución, duplicados históricos y calidad de `raw_pagos`.
2. Existencia de más de una resolución activa por `raw_pago_id`; debe comprobarse antes de confiar en unicidad histórica o plantear una columna generada única.
3. Semántica de duplicado cuando difieren solo `ACUMULADO` o `COMENTARIO`.
4. Tratamiento de CSV (delimitadores y encodings reales) y de celdas numéricas Excel con ceros visuales.
5. Política de retención de archivos y errores.
6. Si `MOTIVO` es obligatorio también en la identificación inicial; arquitectura recomienda que sí.
7. Objetivos medibles de rendimiento, ventana de carga y concurrencia esperada.
8. Mecanismo operativo disponible (`systemd` o Supervisor) y usuario/grupo de servicio.
9. Privilegios definitivos del usuario de aplicación si las vistas se convierten a `SQL SECURITY INVOKER`.

## 18. Carteras — fundación multientidad, BBVA v1, Caja Arequipa v1 y Compartamos v1

La cartera no comparte una tabla Bronze universal. Cada entidad conserva su contrato físico y su evolución de versiones, mientras Silver expone un modelo común:

```text
CARTERA
   ↓
Entidad financiera + versión de perfil
   ↓
raw_cartera_<entidad> (Bronze propio e inmutable)
   ↓
cartera_operaciones
   ├── cartera_contactos
   ├── cartera_direcciones
   ├── cartera_caja_arequipa_detalle (solo Caja Arequipa)
   ├── cartera_compartamos_detalle (solo Compartamos)
   ├── cartera_avales (cuando la fuente los expone)
   └── cartera_garantias (cuando la fuente las expone)
```

`import_batch` incorpora `entidad` y `perfil_version` como dimensiones separadas de `tipo`. Las combinaciones implementadas son `CARTERA / BBVA / 1`, `CARTERA / CAJA_AREQUIPA / 1` y `CARTERA / COMPARTAMOS / 1`. Una futura modificación de formato crea una versión nueva sin reinterpretar archivos históricos.

### 18.1 Contrato multientidad

| Entidad | documento_cliente | cuenta | operacion |
|---|---|---|---|
| BBVA | `numdoc` | `CODCENTRAL` | `CONTRATO` |
| Caja Arequipa | `NRO_DOC_TIT` | `CUENTA` | `OPERACION` |
| Compartamos | `NumDoc` | `Ctacliente` | `Operación` |
| Confianza | `DNI` | `Cuenta Cliente` | `Operación` |
| Wandoo | `DNI` | exactamente `"0" + DNI` | `Numero de Prestamo` |

BBVA v1, Caja Arequipa v1 y Compartamos v1 están implementados. Las demás filas documentan contratos futuros y no habilitan loaders ni cargas. Para Wandoo no se usa `LPAD`: incluso un DNI que ya empieza con cero recibe exactamente un cero adicional al inicio de la cuenta derivada.

### 18.2 Perfil BBVA v1

El perfil declara encabezados, tipos, reglas y mapping. La política estructural es estricta: columnas faltantes, duplicadas o adicionales generan `ERROR` antes de insertar. Esta decisión evita asignar silenciosamente un formato nuevo al perfil v1; una variación aprobada se modelará como perfil v2.

| Campo BBVA | Bronze | Silver |
|---|---|---|
| `CODCENTRAL` | mismo nombre y texto | `cartera_operaciones.cuenta` |
| `CONTRATO` | mismo nombre y texto | `cartera_operaciones.operacion` |
| `CLAVE` | mismo nombre | no se fuerza al modelo común |
| `DESJUDICIA` | mismo nombre | no se fuerza al modelo común |
| `DOCUMENTO` | mismo nombre y texto | `identificador_origen` |
| `UGA` | mismo nombre y texto | no se fuerza al modelo común |
| `TERRITORIO` | mismo nombre | `territorio` |
| `NOMBRE` | mismo nombre | `nombre_cliente` |
| `MONEDA` | mismo nombre | `moneda` |
| `Suma de Importes` | texto fuente | `saldo_capital` como `DECIMAL(15,2)` |
| `Suma de INTERES` | texto fuente | `interes` como `DECIMAL(15,2)` |
| `Suma de MORA` | texto fuente | `mora` como `DECIMAL(15,2)` |
| `OFICINA` | mismo nombre y texto | `oficina` |
| `NOMB_OF` | mismo nombre | `agencia` |
| `FECHAVEN` | representación fuente | `fecha_vencimiento` como `DATE` |
| `PRODUCTO` | mismo nombre | `producto` |
| `DESCPROD` | mismo nombre | `descripcion_producto` |
| `tipodoc` | mismo nombre | `tipo_documento` |
| `numdoc` | mismo nombre y texto | `documento_cliente` |
| `direccion` | mismo nombre | `cartera_direcciones.direccion` |
| `REFE` | mismo nombre | `cartera_direcciones.referencia` |
| `referencia1` | mismo nombre | `cartera_direcciones.referencia1` |
| `referencia2` | mismo nombre | `cartera_direcciones.referencia2` |
| `ubicacion` | mismo nombre | `cartera_direcciones.ubicacion` |
| `codpostal` | mismo nombre y texto | `cartera_direcciones.codigo_postal` |
| `ubigeo` | mismo nombre y texto | operaciones y direcciones: `ubigeo` |
| `dpto` | mismo nombre | operaciones y direcciones: `departamento` |
| `provincia` | mismo nombre | operaciones y direcciones: `provincia` |
| `distrito` | mismo nombre | operaciones y direcciones: `distrito` |
| `tipofono1..5` | nombres originales | cinco posibles filas `cartera_contactos.tipo` |
| `prefijo1..5` | nombres originales y texto | `cartera_contactos.prefijo` |
| `fono1..5` | nombres originales y texto | `cartera_contactos.telefono` |
| `extension1..5` | nombres originales y texto | `cartera_contactos.extension` |
| `NOMB_ESTUD` | mismo nombre | no se fuerza al modelo común |
| `nomb_est_saehost` | mismo nombre | no se fuerza al modelo común |
| `COSECHA` | mismo nombre y texto | `cosecha` |

Los identificadores permanecen texto y conservan ceros, guiones y formatos alfanuméricos. `deuda_total` queda `NULL`; no se aplica una fórmula no confirmada. Cada fila válida produce primero su Raw y luego su operación/contactos/dirección dentro de la misma transacción corta. `source_raw_id` conserva la navegación exacta a Bronze. No se agregan foreign keys entre esquemas ni restricciones únicas de negocio en esta fase; se usan índices de trazabilidad y consulta.

El snapshot resuelve la estructura física, pero no el estado de los datos ni los planes de ejecución. Cualquier cambio DDL se entrega como script revisable con precondiciones, impacto, verificación y rollback; no se aplica implícitamente desde una request web.

### 18.3 Perfil Caja Arequipa v1

El perfil exige exactamente 66 columnas, terminadas en `COSECHA`, y valida nombre y posición después de eliminar espacios exteriores del encabezado. Las dos ocurrencias fuente de `NRO_DOC_TIT` se conservan internamente como `NRO_DOC_TIT_1` y `NRO_DOC_TIT_2`; ambas participan en `row_hash`. Si coinciden se usa el valor, si solo una está informada se usa esa y si difieren o ambas están vacías la fila se registra como error. Los ceros iniciales nunca se eliminan. Caja Arequipa v1 no proporciona un identificador adicional de origen, por lo que `cartera_operaciones.identificador_origen` permanece `NULL`.

`raw_cartera_caja_arequipa` conserva las 66 posiciones; la segunda ocurrencia se persiste físicamente como `NRO_DOC_TIT_2` porque MySQL no permite nombres repetidos. Los ocho campos fuente de texto libre largo (`DIR_LEGAL`, `REF_LEGAL`, `DIR_GES`, `REF_GES`, `ACTIVIDAD`, `DIR_NEG`, `DIR_AVAL` y `REF_AVAL`) usan `TEXT` para conservar contenido fuera de la fila InnoDB y evitar `ERROR 1118` en MySQL 5.7 con `utf8mb4`. El modelo común recibe documento, cuenta, operación, titular, moneda, saldos, deuda, interés, mora, fechas, atraso, producto, agencia y geografía global. Los campos exclusivos se tipan en `cartera_caja_arequipa_detalle`, incluida `provision` como `DECIMAL(15,4)` sin convertirla a porcentaje.

Los teléfonos de titular y gestión se extraen desde celdas que pueden contener varios valores, se validan como celulares peruanos canónicos `9XXXXXXXX` y se insertan en orden determinístico en `cartera_contactos`; el teléfono del aval permanece en `cartera_avales`. `COSECHA` elimina whitespace solo al producir Silver, mientras Bronze conserva el texto fuente. Las direcciones `LEGAL`, `GESTION` y `NEGOCIO` solo se crean si su propio bloque contiene información, sin copiar la geografía global de la operación. El único bloque fuente de aval produce como máximo una fila, aunque `NRO_AVALES` informe otra cantidad. Cada par `TIP_GARn` / `MTO_GARn` produce una garantía cuando al menos uno de los dos valores existe, preservando garantías parciales.

Las fechas aceptan valores `date`/`datetime`, texto en formatos explícitos y seriales Excel convertidos con el epoch real del workbook. Los importes reutilizan el normalizador `Decimal(15,2)` y su tolerancia acotada para ruido binario de celdas XLSX. Una fila válida inserta Bronze, operación, detalle y todos sus hijos en la misma transacción corta del chunk; una falla revierte el chunk completo.

### 18.4 Perfil Compartamos v1

Compartamos exige exactamente 30 posiciones, con nombre y orden canónicos después de eliminar whitespace exterior, incluido NBSP. `NumDoc`, `Ctacliente` y `Operación` se conservan como texto y alimentan respectivamente `documento_cliente`, `cuenta` y `operacion`; `Documento` permanece como atributo auxiliar en `cartera_compartamos_detalle`. Como la fuente no aporta otro identificador confirmado, `identificador_origen` queda `NULL`.

Los cinco importes se normalizan con `Decimal`; `TipCambio` usa `DECIMAL(18,6)` sin transformar cero en `NULL` ni ejecutar conversión de moneda. `FecCastigo` y `FecNacimiento` aceptan fechas explícitas, valores nativos y seriales Excel con el epoch del workbook. `FecDesembolso` admite un año aislado o una fecha completa: el año se valida en el rango `1900..2100` y se persiste siempre que esté disponible como `cartera_compartamos_detalle.anio_desembolso`; una fecha completa también se conserva en `cartera_operaciones.fecha_desembolso`, mientras un año aislado deja ese campo en `NULL`. Bronze conserva el valor fuente sin reinterpretar un año como serial Excel. Las direcciones generan bloques `CLIENTE` y `NEGOCIO` solo cuando contienen información.

BBVA, Caja Arequipa y Compartamos comparten un normalizador telefónico que conserva exclusivamente celulares peruanos `9XXXXXXXX`. También acepta `51` seguido de un celular peruano y elimina ese prefijo; no admite otros códigos de país ni agrega uno. Los valores vacíos, los fijos, las longitudes distintas de nueve y los nueve dígitos repetitivos se descartan. Las coincidencias se deduplican únicamente dentro de la misma operación, después de normalizar y conservando la primera aparición. No existe deduplicación global.
