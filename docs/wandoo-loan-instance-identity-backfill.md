# Backfill controlado de identificador técnico Wandoo

Este procedimiento es manual y no se ejecuta automáticamente al desplegar el código. Solo aplica a filas históricas de `kp_silver.cartera_operaciones` con `entidad = 'WANDOO'` e `identificador_origen IS NULL`. No elimina, reprocesa ni cambia Bronze, `operacion`, saldos, `batch_id` o `source_raw_id`.

La referencia `WAN1:` no es un ID oficial de Wandoo. Se deriva únicamente de DNI, número de préstamo y fecha de otorgamiento. Para reproducir el algoritmo Python en MySQL se usa la siguiente serialización ASCII: `WAN1|<bytes_dni>:<hex_dni>|<bytes_operacion>:<hex_operacion>|10:<hex_fecha_iso>`.

## Preflight de solo lectura

Ejecutar fuera de una publicación Wandoo y guardar los resultados por batch:

```sql
SELECT
    batch_id,
    COUNT(*) AS operaciones_wandoo,
    SUM(identificador_origen IS NULL) AS pendientes,
    SUM(fecha_desembolso IS NULL) AS sin_fecha_otorgamiento
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
GROUP BY batch_id
ORDER BY batch_id;
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
  AND operation.identificador_origen IS NULL
  AND operation.fecha_desembolso IS NOT NULL
  AND (
      detail.id IS NULL
      OR NOT (detail.fecha_otorgamiento_credito <=> operation.fecha_desembolso)
  )
GROUP BY operation.batch_id;
```

## Auditoría de colisiones y simulación

Las colisiones son esperables cuando dos filas tienen exactamente la misma identidad derivada; no se eliminan ni se vuelven únicas.

```sql
SELECT
    documento_cliente,
    operacion,
    fecha_desembolso,
    COUNT(*) AS filas,
    GROUP_CONCAT(CONCAT(id, ':', batch_id, ':', source_raw_id) ORDER BY id) AS trazas
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND fecha_desembolso IS NOT NULL
GROUP BY documento_cliente, operacion, fecha_desembolso
HAVING COUNT(*) > 1;
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
                OCTET_LENGTH(documento_cliente), ':', HEX(CONVERT(documento_cliente USING utf8mb4)), '|',
                OCTET_LENGTH(operacion), ':', HEX(CONVERT(operacion USING utf8mb4)), '|',
                '10:', HEX(DATE_FORMAT(fecha_desembolso, '%Y-%m-%d'))
            ),
            256
        )
    ) AS identificador_simulado
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND identificador_origen IS NULL
  AND fecha_desembolso IS NOT NULL
ORDER BY batch_id, source_raw_id;
```

## Actualización controlada y verificación

Después de aprobar los preflight, tomar respaldo lógico de las filas Wandoo afectadas, detener publicaciones Wandoo y ejecutar el `UPDATE` en una única transacción. Mantener la condición `identificador_origen IS NULL` para que el paso sea idempotente y nunca reemplace referencias existentes.

```sql
START TRANSACTION;

UPDATE kp_silver.cartera_operaciones
SET identificador_origen = CONCAT(
    'WAN1:',
    SHA2(
        CONCAT(
            'WAN1|',
            OCTET_LENGTH(documento_cliente), ':', HEX(CONVERT(documento_cliente USING utf8mb4)), '|',
            OCTET_LENGTH(operacion), ':', HEX(CONVERT(operacion USING utf8mb4)), '|',
            '10:', HEX(DATE_FORMAT(fecha_desembolso, '%Y-%m-%d'))
        ),
        256
    )
)
WHERE entidad = 'WANDOO'
  AND identificador_origen IS NULL
  AND fecha_desembolso IS NOT NULL;

SELECT ROW_COUNT() AS filas_actualizadas;

SELECT
    COUNT(*) AS pendientes_con_fecha
FROM kp_silver.cartera_operaciones
WHERE entidad = 'WANDOO'
  AND identificador_origen IS NULL
  AND fecha_desembolso IS NOT NULL;

COMMIT;
```

Después, repetir la simulación y comprobar que cada fila con fecha tiene exactamente el valor calculado. Las filas sin fecha deben conservar `identificador_origen = NULL`. Para revertir, restaurar únicamente las filas afectadas desde el respaldo previo; no se debe inferir una fecha ni elegir valores de otros préstamos o batches.
