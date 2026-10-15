# KP SEARCH GOLD CONTRACT

Version: 1.0  
Dataset: PERSONAS

## Objeto publicado

- Schema: `kp_gold`
- Objeto: `search_person_index`
- Motor: InnoDB (MySQL 5.7.33)
- Cardinalidad: exactamente cero o una fila por `documento`.
- Consumidor: KP-Search, mediante igualdad exacta por documento.

| Columna | Tipo MySQL | Nullable | Semántica |
|---|---|---:|---|
| documento | VARCHAR(20) | No | DNI v1 de ocho dígitos; PK operativa. |
| tipo_documento | VARCHAR(20) ASCII | No | En v1 siempre `DNI`. |
| nombre_completo | VARCHAR(500) | Sí | Composición normalizada `nombres paterno materno`. |
| paterno | VARCHAR(150) | Sí | Apellido paterno normalizado. |
| materno | VARCHAR(150) | Sí | Apellido materno normalizado. |
| nombres | VARCHAR(255) | Sí | Nombres normalizados. |
| fecha_nacimiento | DATE | Sí | Fecha válida de nacimiento. |
| sexo | VARCHAR(50) | Sí | Código textual de la fuente, sin interpretación semántica. |
| estado_civil | VARCHAR(100) | Sí | Estado civil normalizado técnicamente. |
| direccion_origen | TEXT | Sí | Dirección recibida en PERSONAS; no sustituye al futuro dataset DIRECCIONES. |
| source_code | VARCHAR(64) ASCII | No | Procedencia empresarial estable autorizada. |
| batch_id | BIGINT UNSIGNED | No | Batch Silver que publicó la versión operativa. |
| updated_at | DATETIME | No | Fecha UTC de publicación en Gold. |

## Claves e índices

- `PRIMARY KEY (documento)` garantiza una identidad operativa por documento.
- `idx_search_person_index_source_batch (source_code, batch_id)` soporta auditoría y verificación de publicación.
- `idx_search_person_index_updated (updated_at)` soporta observabilidad por corte.

## Política de fuentes

DM-F2 autoriza una sola fuente activa para PERSONAS. El publicador bloquea una segunda fuente y no aplica precedencia por fecha, `MAX(batch_id)`, orden alfabético, `INSERT IGNORE` ni `REPLACE INTO`. `BASE_PERSONAS` es únicamente un código técnico provisional propuesto; debe registrarse manualmente solo después de confirmar el nombre empresarial real.

## Semántica de actualización

- `SCOPE_REPLACE`: dentro de una transacción, elimina de Gold exclusivamente los documentos del scope oficial del batch y los inserta desde Silver validado.
- `FULL_REPLACE`: Silver del batch actúa como población validada. Dentro de una transacción se hace upsert de esa población y luego se eliminan únicamente filas Gold cuyo `batch_id` no es el batch actual. Así se evita dejar Gold vacío antes de insertar y se conserva atomicidad.
- Bronze y Silver son históricos append-only/por batch y no se eliminan durante la publicación.
- `kp_control`, `kp_silver` y `kp_gold` deben residir en la misma instancia MySQL y las tablas participantes deben ser InnoDB para que la transacción multi-schema sea atómica.

Para volúmenes futuros, una generación Gold con tabla física versionada y puntero de versión reduciría el tiempo de bloqueo. No forma parte de v1 porque cambiaría el contrato físico y la consulta directa aprobada. `RENAME TABLE` tampoco se usa: en MySQL produce commits implícitos e impediría confirmar atómicamente el estado del batch.

## Consulta recomendada

```sql
SELECT
    documento,
    tipo_documento,
    nombre_completo,
    paterno,
    materno,
    nombres,
    fecha_nacimiento,
    sexo,
    estado_civil,
    direccion_origen,
    source_code,
    batch_id,
    updated_at
FROM kp_gold.search_person_index
WHERE documento = ?
LIMIT 1;
```
