# KP SEARCH TELEFONOS GOLD CONTRACT

Version: 1.0  
Dataset: TELEFONOS

## Objeto publicado

- Schema: `kp_gold`
- Objeto: `search_telefonos`
- Motor: InnoDB (MySQL 5.7.33)
- Cardinalidad: cero o más teléfonos vigentes por `documento`; cada par documento/teléfono es único.
- Consumidor: KP-Search mediante igualdad exacta por documento.

| Columna | Tipo MySQL | Nullable | Semántica |
|---|---|---:|---|
| documento | VARCHAR(20) | No | DNI v1 de ocho dígitos ASCII. |
| telefono | CHAR(9) ASCII | No | Celular `9XXXXXXXX`; no contiene formato ni código de país. |
| operador | VARCHAR(32) ASCII | No | Operador homologado con la lista cerrada v1. |
| fecha_data | DATE | No | Fecha declarada en `FECHA DATA`; no se deriva de `OPERADOR`. |
| source_code | VARCHAR(64) ASCII | No | Procedencia empresarial estable autorizada. |
| batch_id | BIGINT UNSIGNED | No | Batch Silver que publicó el estado vigente. |
| updated_at | DATETIME | No | Fecha UTC de publicación en Gold. |

## Claves e índices

- `PRIMARY KEY (documento, telefono)` garantiza unicidad operativa del vínculo.
- `idx_search_telefonos_document_date (documento, fecha_data)` soporta consulta y orden temporal por documento.
- `idx_search_telefonos_source_batch (source_code, batch_id)` soporta auditoría y verificación de publicación.

## Reglas de teléfono

El valor fuente se convierte a texto, se recorta y debe coincidir exactamente con `^9[0-9]{8}$`. También se rechazan números de un solo dígito repetido y los valores explícitos `900000000` y `911111111`. No se aplican heurísticas contra secuencias como `912345678` o `987654321`.

## Operadores v1

`SUNAT`, `MOVISTAR`, `BITEL`, `CLARO`, `ENTEL`, `WIN`, `FLASH`, `GUINEA`, `VIRGIN`, `MINSA`, `FLASH MOBILE`, `GUINEA MOBILE`, `ESSALUD`.

La detección es case-insensitive, aplica trim, colapsa whitespace y busca nombres completos en cualquier posición respetando límites de palabra. Los operadores se ordenan por longitud descendente, por lo que `FLASH MOBILE` y `GUINEA MOBILE` tienen precedencia sobre sus nombres cortos. Si aparecen dos operadores canónicos diferentes, la fila queda como `OPERATOR_AMBIGUOUS`; un valor sin coincidencias queda como `OPERATOR_INVALID`.

## Trazabilidad y hashes

Bronze usa el `row_hash` común SEARCH: SHA-256 del UTF-8 de un JSON compacto y determinístico con versión, posición, header, tipo explícito y valor de cada una de las cuatro celdas fuente. `NULL`, vacío, cero y texto `"0"` son representaciones diferentes.

Silver usa `record_hash`: SHA-256 del JSON canónico de los valores normalizados, exactamente en este orden: `documento`, `telefono`, `operador_raw`, `operador`, `fecha_data`. La fecha se serializa como ISO `YYYY-MM-DD` y cada valor conserva tipo explícito. Ninguno de los hashes se usa para descartar historia.

## Política de fuentes

DM-F3 autoriza una sola fuente activa para TELEFONOS. `BASE_TELEFONOS` es el código técnico propuesto para esta procedencia y debe registrarse manualmente. `OPERADOR` es un atributo funcional y nunca se usa como `source_code`. El publicador bloquea una segunda fuente hasta que exista una política formal de precedencia o fusión.

## Semántica de actualización

- `SCOPE_REPLACE`: elimina de Gold todos los teléfonos de los documentos del scope oficial del batch y luego inserta el conjunto completo Silver del batch para esos documentos.
- `FULL_REPLACE`: hace upsert set-based de la población validada y elimina filas Gold cuyo `batch_id` no corresponde al batch nuevo, todo dentro de la misma transacción.
- Bronze y Silver permanecen históricos. No se usa `TRUNCATE`, `REPLACE INTO` ni `INSERT IGNORE`.
- `kp_control`, `kp_bronze`, `kp_silver` y `kp_gold` deben residir en la misma instancia y usar InnoDB para garantizar atomicidad multi-schema.

## Consulta recomendada

```sql
SELECT
    documento,
    telefono,
    operador,
    fecha_data,
    source_code,
    batch_id,
    updated_at
FROM kp_gold.search_telefonos
WHERE documento = ?
ORDER BY fecha_data DESC, telefono ASC;
```
