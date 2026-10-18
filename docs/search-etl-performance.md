# SEARCH ETL: rendimiento y presupuesto operativo

## Alcance

Este documento describe la instrumentación y los límites operativos del ETL SEARCH. Bronze continúa append-only, Silver conserva histórico por batch y Gold se publica en una única transacción InnoDB junto con la metadata final de `import_batch`.

## Métricas

El worker emite `search_phase_metric` con tiempos monotónicos de:

- `parse_normalize`
- `bronze_insert`
- `bronze_id_lookup`
- `silver_insert`
- `scope_lookup`
- `scope_insert`
- `dedup_lookup` (datasets que deduplican técnicamente)
- `preflight`
- `gold_source_validation`
- `gold_insert`
- `gold_delete`
- `integrity_validation`
- `batch_final_lock`
- `batch_finalize`
- `commit`
- `total`

Cada evento contiene identificadores técnicos del batch y dataset, duración, filas, rendimiento, llamadas lógicas, llamadas `executemany` y statements físicos observados por el cursor. En `gold_delete`, las filas corresponden al `rowcount` real del DML, sin una consulta adicional. No contiene SQL, bindings, documentos, nombres, payloads, rutas ni credenciales.

`peak_memory_mb` utiliza el máximo residente reportado por el sistema operativo cuando Python ofrece `resource.getrusage`. En Windows queda `null`: no se activa `tracemalloc` en producción porque alteraría el rendimiento que se intenta medir.

Las llamadas lógicas no equivalen necesariamente a paquetes físicos. El cursor instrumentado cuenta cada `execute` que PyMySQL genera, incluidos los fragmentos internos de un `executemany` cuando el statement construido supera su límite. `COMMIT` se contabiliza como operación lógica de su fase, pero no como statement físico porque no atraviesa `Cursor.execute`; la apertura de transacción no se publica como una fase independiente.

## Presupuesto de timeouts

Valores predeterminados:

| Capa | Configuración | Valor | Semántica |
|---|---|---:|---|
| Conexión PyMySQL | `ETL_DB_CONNECT_TIMEOUT` | 15 s | Apertura de conexión |
| Lectura PyMySQL | `ETL_DB_READ_TIMEOUT` | 600 s | Espera de respuesta de una operación |
| Escritura PyMySQL | `ETL_DB_WRITE_TIMEOUT` | 600 s | Escritura del cliente hacia MySQL |
| Proceso Python | `ETL_PROCESS_TIMEOUT_SECONDS` | 3600 s | Presupuesto total controlado por Symfony Process |
| Job Laravel | `ETL_JOB_TIMEOUT_SECONDS` | 3660 s | Debe superar al proceso Python |
| Reserva de cola DB | `DB_QUEUE_RETRY_AFTER` | 3720 s | Debe superar al timeout del Job |
| Lock de publicación | `ETL_SEARCH_PUBLICATION_LOCK_TIMEOUT` | 10 s | Espera máxima para otra publicación del mismo dataset/source |

No se configura idle timeout para Symfony Process. Durante un `INSERT ... SELECT` válido puede no existir salida por varios minutos; el límite total y los timeouts del driver ya acotan la operación.

En PHP CLI, `max_execution_time` debe permanecer en `0`. En Windows/Laragon, el límite fiable del subproceso es Symfony Process; las señales del worker de cola no tienen las mismas garantías que en Linux con PCNTL. El Job tiene un solo intento y no reinicia automáticamente una importación parcial.

Los valores no deben ampliarse para ocultar consultas lentas. Si el percentil alto de una fase se acerca a su presupuesto, primero se revisan sus métricas y el plan `EXPLAIN` en un entorno autorizado.

## Concurrencia y atomicidad

La publicación adquiere un `GET_LOCK` con nombre derivado mediante SHA-256 de dataset/source. El lock:

- serializa publicaciones del mismo dataset/source;
- tiene espera acotada;
- se libera en `finally`;
- se libera por MySQL si la conexión desaparece;
- no sustituye la transacción InnoDB.

Dentro de la transacción se publica Gold, se valida integridad, se bloquea brevemente `import_batch`, se revalida source y se actualiza metadata. Gold y metadata hacen un único commit. Cualquier fallo anterior al commit revierte la publicación.

## Chunks y benchmarks

El valor predeterminado continúa en 5,000 filas. Los tamaños 2,000, 5,000 y 10,000 deben compararse con datos sintéticos y, posteriormente, con MySQL aislado. Se medirán:

- duración por fase;
- máximo de filas retenidas por chunk;
- llamadas lógicas y físicas;
- memoria pico;
- redo/undo y duración de commit;
- tamaño medio de `raw_payload`.

Las pruebas masivas sintéticas son opt-in mediante `RUN_ETL_MASS_TESTS=1`. Los benchmarks con MySQL permanecen pendientes de autorización.

## FULL_REPLACE

Se conserva el algoritmo actual `INSERT/UPSERT -> DELETE antiguo`. La alternativa `DELETE antiguo -> INSERT` requiere benchmark por dataset porque cambia el costo de índices, locks, redo/undo y espacio temporal. No se utilizarán `TRUNCATE`, `RENAME TABLE` ni DDL dentro de la publicación.
