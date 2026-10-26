# Backfill controlado de identificador técnico Wandoo

Este procedimiento es manual y no se ejecuta automáticamente al desplegar el código. Su primer alcance operativo está limitado estrictamente a `batch_id = 29`, con `entidad = 'WANDOO'` e `identificador_origen IS NULL`. No elimina, reprocesa ni cambia Bronze, `operacion`, saldos, `batch_id` o `source_raw_id`. Ampliar el alcance requiere un procedimiento aprobado por separado.

La referencia `WAN1:` no es un ID oficial de Wandoo. Se deriva únicamente de DNI, número de préstamo y fecha de otorgamiento. Para reproducir el algoritmo Python en MySQL se usa la siguiente serialización ASCII: `WAN1|<bytes_dni>:<hex_dni>|<bytes_operacion>:<hex_operacion>|10:<hex_fecha_iso>`.

## Preflight de solo lectura

No iniciar el backfill hasta cumplir todos estos requisitos: conteos preflight, cero colisiones de identidad en el batch 29, coincidencia del vector Python/MySQL, respaldo actual de las filas objetivo, ausencia de importaciones Wandoo concurrentes y revisión de las filas simuladas.

Ejecutar los siguientes controles de solo lectura y guardar los resultados:

```sql
SELECT
    batch_id,
    COUNT(*) AS operaciones_wandoo,
    SUM(identificador_origen IS NULL) AS pendientes,
    SUM(fecha_desembolso IS NULL) AS sin_fecha_otorgamiento
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND batch_id = 29
GROUP BY batch_id;
```

La fecha se confirma también contra el detalle de Wandoo, sin elegir otra fila ni otro batch:

```sql
SELECT
    operation.batch_id,
    COUNT(*) AS sin_fecha_coherente
FROM kp_silver.cartera_operaciones AS operation
LEFT JOIN kp_silver.cartera_wandoo_detalle AS detail
    ON detail.operacion_id = operation.id
   AND detail.batch_id = operation.batch_id
   AND detail.source_raw_id = operation.source_raw_id
WHERE operation.entidad = 'WANDOO'
  AND operation.batch_id = 29
  AND operation.identificador_origen IS NULL
  AND operation.fecha_desembolso IS NOT NULL
  AND (
      detail.id IS NULL
      OR NOT (detail.fecha_otorgamiento_credito <=> operation.fecha_desembolso)
  )
GROUP BY operation.batch_id;
```

Comprobar que no exista una importación Wandoo concurrente:

```sql
SELECT batch_id, estado, fecha_inicio, archivo_original
FROM kp_control.import_batch
WHERE tipo = 'CARTERA'
  AND entidad = 'WANDOO'
  AND estado = 'PROCESANDO';
```

## Auditoría de colisiones, vector de comprobación y simulación

La referencia derivada no establece unicidad empresarial. Sin embargo, esta primera ejecución exige cero colisiones en el batch 29; si la consulta devuelve filas, detenerse y revisar el caso antes de actualizar.

```sql
SELECT
    documento_cliente,
    operacion,
    fecha_desembolso,
    COUNT(*) AS filas,
    GROUP_CONCAT(CONCAT(id, ':', batch_id, ':', source_raw_id) ORDER BY id) AS trazas
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND batch_id = 29
  AND fecha_desembolso IS NOT NULL
GROUP BY documento_cliente, operacion, fecha_desembolso
HAVING COUNT(*) > 1;
```

El siguiente `SELECT` debe devolver exactamente el hash esperado y `coincide_con_python = 1`. Es una prueba únicamente de lectura de la equivalencia entre Python (`bytes.hex()` en minúsculas) y MySQL:

```sql
SELECT
    vector.identificador_calculado,
    'WAN1:6dae9d76c2ca5fd26795c65ef9e08ddf42047158b73678887ef1857daaaec7d5'
        AS identificador_esperado,
    vector.identificador_calculado =
        'WAN1:6dae9d76c2ca5fd26795c65ef9e08ddf42047158b73678887ef1857daaaec7d5'
        AS coincide_con_python
FROM (
    SELECT CONCAT(
        'WAN1:',
        SHA2(
            CONCAT(
                'WAN1|',
                OCTET_LENGTH('00003862'), ':',
                LOWER(HEX(CONVERT('00003862' USING utf8mb4))), '|',
                OCTET_LENGTH('7277-1292-001'), ':',
                LOWER(HEX(CONVERT('7277-1292-001' USING utf8mb4))), '|',
                '10:',
                LOWER(HEX(DATE_FORMAT(CAST('2025-09-05' AS DATE), '%Y-%m-%d')))
            ),
            256
        )
    ) AS identificador_calculado
) AS vector;
```

Simular primero los valores que se actualizarían, sin escribir:

```sql
SELECT
    id,
    batch_id,
    source_raw_id,
    documento_cliente,
    operacion,
    fecha_desembolso,
    CONCAT(
        'WAN1:',
        SHA2(
            CONCAT(
                'WAN1|',
                OCTET_LENGTH(documento_cliente), ':', LOWER(HEX(CONVERT(documento_cliente USING utf8mb4))), '|',
                OCTET_LENGTH(operacion), ':', LOWER(HEX(CONVERT(operacion USING utf8mb4))), '|',
                '10:', LOWER(HEX(DATE_FORMAT(fecha_desembolso, '%Y-%m-%d')))
            ),
            256
        )
    ) AS identificador_simulado
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND batch_id = 29
  AND identificador_origen IS NULL
  AND fecha_desembolso IS NOT NULL
ORDER BY batch_id, source_raw_id;
```

## Actualización controlada y verificación

Después de aprobar los preflight, tomar un respaldo actual exclusivamente de las filas Wandoo del batch 29, confirmar que la consulta de importaciones concurrentes no devuelve filas y revisar la simulación fila por fila. Solo entonces se podrá proponer el `UPDATE` en una ventana controlada. Mantener las condiciones `batch_id = 29` e `identificador_origen IS NULL` para que el paso sea idempotente y nunca reemplace referencias existentes. No ejecutar esta plantilla sin aprobación operativa explícita.

```sql
START TRANSACTION;

UPDATE kp_silver.cartera_operaciones
SET identificador_origen = CONCAT(
    'WAN1:',
    SHA2(
        CONCAT(
            'WAN1|',
            OCTET_LENGTH(documento_cliente), ':', LOWER(HEX(CONVERT(documento_cliente USING utf8mb4))), '|',
            OCTET_LENGTH(operacion), ':', LOWER(HEX(CONVERT(operacion USING utf8mb4))), '|',
            '10:', LOWER(HEX(DATE_FORMAT(fecha_desembolso, '%Y-%m-%d')))
        ),
        256
    )
)
WHERE entidad = 'WANDOO'
  AND batch_id = 29
  AND identificador_origen IS NULL
  AND fecha_desembolso IS NOT NULL;

SELECT ROW_COUNT() AS filas_actualizadas;

SELECT
    COUNT(*) AS pendientes_con_fecha
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND batch_id = 29
  AND identificador_origen IS NULL
  AND fecha_desembolso IS NOT NULL;

SELECT
    id,
    batch_id,
    source_raw_id,
    identificador_origen
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND batch_id = 29
  AND identificador_origen IS NOT NULL
ORDER BY source_raw_id;

COMMIT;
```

Después, repetir la simulación y comprobar que cada fila con fecha tiene exactamente el valor calculado. Las filas sin fecha deben conservar `identificador_origen = NULL`. Para revertir, restaurar únicamente las filas afectadas desde el respaldo previo; no se debe inferir una fecha ni elegir valores de otros préstamos o batches.
