-- KP Data Manager - Fase 1C / conciliación preliminar de asignación 202610
-- SOLO LECTURA. Ejecutable antes de aplicar el SQL 059: usa únicamente tablas
-- existentes de kp_silver. No expone datos personales.
-- Batches candidatos de diagnóstico: BBVA 7, CAJA_AREQUIPA 14, COMPARTAMOS 21,
-- CONFIANZA 26, WANDOO 29 y PERSONAS 44. No son una aprobación de publicación.
-- No genera una fotografía oficial ni aplica un corte temporal: la fecha de
-- corte y la promoción de una generación se definen en el proceso posterior.

-- 1. Inventario de operaciones/documentos por batch, cosecha canónica y moneda.
SELECT source.entidad, source.batch_id, source.cosecha_origen, source.cosecha_canonica,
       source.moneda_original, COUNT(*) AS operaciones,
       COUNT(DISTINCT source.documento_cliente) AS documentos
FROM (
    SELECT operation_row.entidad, operation_row.batch_id, operation_row.cosecha AS cosecha_origen,
           CASE
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 2' THEN 'CONFIANZA_2'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 3' THEN 'CONFIANZA_3'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 4' THEN 'CONFIANZA_4'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 5' THEN 'CONFIANZA_5'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 6' THEN 'CONFIANZA_6'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 7' THEN 'CONFIANZA_7'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 8' THEN 'CONFIANZA_8'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 9' THEN 'CONFIANZA_9'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 10' THEN 'CONFIANZA_10'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 11' THEN 'CONFIANZA_11'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 12' THEN 'CONFIANZA_12'
               ELSE operation_row.cosecha
           END AS cosecha_canonica,
           operation_row.documento_cliente, operation_row.moneda AS moneda_original
    FROM kp_silver.cartera_operaciones AS operation_row
    WHERE (operation_row.entidad = 'BBVA' AND operation_row.batch_id = 7)
       OR (operation_row.entidad = 'CAJA_AREQUIPA' AND operation_row.batch_id = 14)
       OR (operation_row.entidad = 'COMPARTAMOS' AND operation_row.batch_id = 21)
       OR (operation_row.entidad = 'CONFIANZA' AND operation_row.batch_id = 26)
       OR (operation_row.entidad = 'WANDOO' AND operation_row.batch_id = 29)
) AS source
GROUP BY source.entidad, source.batch_id, source.cosecha_origen, source.cosecha_canonica, source.moneda_original
ORDER BY source.entidad, source.batch_id, source.cosecha_canonica, source.moneda_original;

-- 2. Inclusión/exclusión contra el catálogo empresarial, sin tocar Silver.
SELECT source.entidad, source.batch_id, source.cosecha_canonica,
       CASE
           WHEN source.entidad = 'BBVA' AND source.cosecha_canonica IN ('BBVA1', 'BBVA2', 'BBVA3', 'BBVA4', 'BBVA5', 'BBVA6', 'BBVA7', 'BBVA8') THEN 'INCLUIBLE_SUJETA_A_OTROS_CONTROLES'
           WHEN source.entidad = 'CAJA_AREQUIPA' AND source.cosecha_canonica IN ('CAJAAQP1', 'CAJAAQP2', 'CAJAAQP3', 'CAJAAQP4', 'CAJAAQP5') THEN 'INCLUIBLE_SUJETA_A_OTROS_CONTROLES'
           WHEN source.entidad = 'COMPARTAMOS' AND source.cosecha_canonica IN ('COMPARTAMOS_1', 'COMPARTAMOS_2', 'COMPARTAMOS_3') THEN 'INCLUIBLE_SUJETA_A_OTROS_CONTROLES'
           WHEN source.entidad = 'CONFIANZA' AND source.cosecha_canonica IN ('CONFIANZA', 'CONFIANZA_2', 'CONFIANZA_3', 'CONFIANZA_4', 'CONFIANZA_5', 'CONFIANZA_6', 'CONFIANZA_7', 'CONFIANZA_8', 'CONFIANZA_9', 'CONFIANZA_10', 'CONFIANZA_11', 'CONFIANZA_12') THEN 'INCLUIBLE_SUJETA_A_OTROS_CONTROLES'
           WHEN source.entidad = 'WANDOO' AND source.cosecha_canonica = 'WANDOO_1' THEN 'INCLUIBLE_SUJETA_A_OTROS_CONTROLES'
           ELSE 'EXCLUIDA_COSECHA_SIN_EQUIVALENCIA_APROBADA'
       END AS clasificacion,
       COUNT(*) AS operaciones, COUNT(DISTINCT source.documento_cliente) AS documentos
FROM (
    SELECT operation_row.entidad, operation_row.batch_id, operation_row.documento_cliente,
           CASE
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 2' THEN 'CONFIANZA_2'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 3' THEN 'CONFIANZA_3'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 4' THEN 'CONFIANZA_4'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 5' THEN 'CONFIANZA_5'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 6' THEN 'CONFIANZA_6'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 7' THEN 'CONFIANZA_7'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 8' THEN 'CONFIANZA_8'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 9' THEN 'CONFIANZA_9'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 10' THEN 'CONFIANZA_10'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 11' THEN 'CONFIANZA_11'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 12' THEN 'CONFIANZA_12'
               ELSE operation_row.cosecha
           END AS cosecha_canonica
    FROM kp_silver.cartera_operaciones AS operation_row
    WHERE (operation_row.entidad = 'BBVA' AND operation_row.batch_id = 7)
       OR (operation_row.entidad = 'CAJA_AREQUIPA' AND operation_row.batch_id = 14)
       OR (operation_row.entidad = 'COMPARTAMOS' AND operation_row.batch_id = 21)
       OR (operation_row.entidad = 'CONFIANZA' AND operation_row.batch_id = 26)
       OR (operation_row.entidad = 'WANDOO' AND operation_row.batch_id = 29)
) AS source
GROUP BY source.entidad, source.batch_id, source.cosecha_canonica, clasificacion
ORDER BY source.entidad, source.batch_id, source.cosecha_canonica, clasificacion;

-- 3. Cobertura financiera por moneda. Para WANDOO_1/PEN, documentos y
-- operaciones son los flg_cliente/flg_cuenta esperados; contrastar 13,042 /
-- 13,044 y capital/deuda S/ 6,615,373.31 con los valores observados.
SELECT operation_row.entidad, operation_row.batch_id,
       CASE
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 2' THEN 'CONFIANZA_2'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 3' THEN 'CONFIANZA_3'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 4' THEN 'CONFIANZA_4'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 5' THEN 'CONFIANZA_5'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 6' THEN 'CONFIANZA_6'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 7' THEN 'CONFIANZA_7'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 8' THEN 'CONFIANZA_8'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 9' THEN 'CONFIANZA_9'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 10' THEN 'CONFIANZA_10'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 11' THEN 'CONFIANZA_11'
           WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 12' THEN 'CONFIANZA_12'
           ELSE operation_row.cosecha
       END AS cosecha_canonica,
       operation_row.moneda AS moneda_original, COUNT(*) AS operaciones,
       COUNT(DISTINCT operation_row.documento_cliente) AS documentos,
       COUNT(DISTINCT operation_row.documento_cliente) AS flg_cliente_esperado,
       COUNT(*) AS flg_cuenta_esperado,
       SUM(operation_row.saldo_capital IS NULL) AS operaciones_sin_capital,
       SUM(operation_row.deuda_total IS NULL) AS operaciones_sin_deuda_total,
       SUM(CASE WHEN operation_row.saldo_capital IS NOT NULL THEN operation_row.saldo_capital END) AS capital_original,
       SUM(CASE WHEN operation_row.deuda_total IS NOT NULL THEN operation_row.deuda_total END) AS deuda_total_original,
       SUM(CASE WHEN operation_row.saldo_capital IS NOT NULL AND operation_row.deuda_total IS NOT NULL THEN operation_row.deuda_total - operation_row.saldo_capital END) AS componentes_no_capital_original
FROM kp_silver.cartera_operaciones AS operation_row
WHERE (operation_row.entidad = 'BBVA' AND operation_row.batch_id = 7)
   OR (operation_row.entidad = 'CAJA_AREQUIPA' AND operation_row.batch_id = 14)
   OR (operation_row.entidad = 'COMPARTAMOS' AND operation_row.batch_id = 21)
   OR (operation_row.entidad = 'CONFIANZA' AND operation_row.batch_id = 26)
   OR (operation_row.entidad = 'WANDOO' AND operation_row.batch_id = 29)
GROUP BY operation_row.entidad, operation_row.batch_id, cosecha_canonica, operation_row.moneda
ORDER BY operation_row.entidad, operation_row.batch_id, cosecha_canonica, operation_row.moneda;

-- 4. Cobertura del único batch PERSONAS 44, sin devolver documentos ni atributos.
SELECT source.entidad, source.batch_id, source.cosecha_canonica,
       COUNT(DISTINCT source.documento_cliente) AS documentos_cartera,
       COUNT(DISTINCT person.documento) AS documentos_en_personas_44,
       COUNT(DISTINCT source.documento_cliente) - COUNT(DISTINCT person.documento) AS documentos_sin_enriquecimiento_44
FROM (
    SELECT operation_row.entidad, operation_row.batch_id, operation_row.documento_cliente,
           CASE
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 2' THEN 'CONFIANZA_2'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 3' THEN 'CONFIANZA_3'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 4' THEN 'CONFIANZA_4'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 5' THEN 'CONFIANZA_5'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 6' THEN 'CONFIANZA_6'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 7' THEN 'CONFIANZA_7'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 8' THEN 'CONFIANZA_8'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 9' THEN 'CONFIANZA_9'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 10' THEN 'CONFIANZA_10'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 11' THEN 'CONFIANZA_11'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 12' THEN 'CONFIANZA_12'
               ELSE operation_row.cosecha
           END AS cosecha_canonica
    FROM kp_silver.cartera_operaciones AS operation_row
    WHERE (operation_row.entidad = 'BBVA' AND operation_row.batch_id = 7)
       OR (operation_row.entidad = 'CAJA_AREQUIPA' AND operation_row.batch_id = 14)
       OR (operation_row.entidad = 'COMPARTAMOS' AND operation_row.batch_id = 21)
       OR (operation_row.entidad = 'CONFIANZA' AND operation_row.batch_id = 26)
       OR (operation_row.entidad = 'WANDOO' AND operation_row.batch_id = 29)
) AS source
LEFT JOIN kp_silver.search_personas AS person
  ON person.batch_id = 44 AND person.documento = source.documento_cliente
GROUP BY source.entidad, source.batch_id, source.cosecha_canonica
ORDER BY source.entidad, source.batch_id, source.cosecha_canonica;

-- 5. Grupos de colisión/solapamiento; el resultado contiene solo conteos.
SELECT collisions.entidad, collisions.cosecha_canonica,
       COUNT(*) AS grupos_con_colision, SUM(collisions.filas) AS filas_en_colision
FROM (
    SELECT operation_row.entidad,
           CASE
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 2' THEN 'CONFIANZA_2'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 3' THEN 'CONFIANZA_3'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 4' THEN 'CONFIANZA_4'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 5' THEN 'CONFIANZA_5'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 6' THEN 'CONFIANZA_6'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 7' THEN 'CONFIANZA_7'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 8' THEN 'CONFIANZA_8'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 9' THEN 'CONFIANZA_9'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 10' THEN 'CONFIANZA_10'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 11' THEN 'CONFIANZA_11'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 12' THEN 'CONFIANZA_12'
               ELSE operation_row.cosecha
           END AS cosecha_canonica,
           COUNT(*) AS filas
    FROM kp_silver.cartera_operaciones AS operation_row
    WHERE (operation_row.entidad = 'BBVA' AND operation_row.batch_id = 7)
       OR (operation_row.entidad = 'CAJA_AREQUIPA' AND operation_row.batch_id = 14)
       OR (operation_row.entidad = 'COMPARTAMOS' AND operation_row.batch_id = 21)
       OR (operation_row.entidad = 'CONFIANZA' AND operation_row.batch_id = 26)
       OR (operation_row.entidad = 'WANDOO' AND operation_row.batch_id = 29)
    GROUP BY operation_row.entidad, cosecha_canonica, operation_row.documento_cliente,
             operation_row.operacion, operation_row.identificador_origen
    HAVING COUNT(*) > 1
) AS collisions
GROUP BY collisions.entidad, collisions.cosecha_canonica
ORDER BY collisions.entidad, collisions.cosecha_canonica;

-- 6. Preparación solarizada preliminar sin tasa sintética. PEN y la
-- política funcional WANDOO_1 usan factor 1; USD queda pendiente de tasa aprobada.
SELECT source.entidad, source.batch_id, source.cosecha_canonica,
       source.moneda_original, source.moneda_resuelta, COUNT(*) AS operaciones,
       SUM(source.moneda_resuelta IS NULL) AS operaciones_sin_moneda,
       SUM(source.moneda_resuelta = 'USD') AS operaciones_usd_pendientes_tipo_cambio,
       CASE WHEN SUM(source.capital_pen IS NULL) = 0 THEN SUM(source.capital_pen) END AS capital_convertido_pen,
       CASE WHEN SUM(source.deuda_pen IS NULL) = 0 THEN SUM(source.deuda_pen) END AS deuda_total_convertida_pen,
       CASE WHEN SUM(source.capital_pen IS NULL) = 0 AND SUM(source.deuda_pen IS NULL) = 0 THEN SUM(source.deuda_pen - source.capital_pen) END AS componentes_no_capital_pen
FROM (
    SELECT operation_row.entidad, operation_row.batch_id, operation_row.moneda AS moneda_original,
           CASE
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 2' THEN 'CONFIANZA_2'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 3' THEN 'CONFIANZA_3'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 4' THEN 'CONFIANZA_4'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 5' THEN 'CONFIANZA_5'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 6' THEN 'CONFIANZA_6'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 7' THEN 'CONFIANZA_7'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 8' THEN 'CONFIANZA_8'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 9' THEN 'CONFIANZA_9'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 10' THEN 'CONFIANZA_10'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 11' THEN 'CONFIANZA_11'
               WHEN operation_row.entidad = 'CONFIANZA' AND operation_row.cosecha = 'CONFIANZA 12' THEN 'CONFIANZA_12'
               ELSE operation_row.cosecha
           END AS cosecha_canonica,
           CASE
               WHEN UPPER(TRIM(operation_row.moneda)) IN ('PEN', 'S/', 'S/.', 'SOLES') THEN 'PEN'
               WHEN UPPER(TRIM(operation_row.moneda)) IN ('USD', 'US$', 'DOLARES', 'DÓLARES') THEN 'USD'
               WHEN operation_row.entidad = 'WANDOO' AND operation_row.cosecha = 'WANDOO_1' THEN 'PEN'
               ELSE NULL
           END AS moneda_resuelta,
           CASE
               WHEN UPPER(TRIM(operation_row.moneda)) IN ('PEN', 'S/', 'S/.', 'SOLES') OR (operation_row.entidad = 'WANDOO' AND operation_row.cosecha = 'WANDOO_1') THEN ROUND(operation_row.saldo_capital, 2)
               ELSE NULL
           END AS capital_pen,
           CASE
               WHEN UPPER(TRIM(operation_row.moneda)) IN ('PEN', 'S/', 'S/.', 'SOLES') OR (operation_row.entidad = 'WANDOO' AND operation_row.cosecha = 'WANDOO_1') THEN ROUND(operation_row.deuda_total, 2)
               ELSE NULL
           END AS deuda_pen
    FROM kp_silver.cartera_operaciones AS operation_row
    WHERE (operation_row.entidad = 'BBVA' AND operation_row.batch_id = 7)
       OR (operation_row.entidad = 'CAJA_AREQUIPA' AND operation_row.batch_id = 14)
       OR (operation_row.entidad = 'COMPARTAMOS' AND operation_row.batch_id = 21)
       OR (operation_row.entidad = 'CONFIANZA' AND operation_row.batch_id = 26)
       OR (operation_row.entidad = 'WANDOO' AND operation_row.batch_id = 29)
) AS source
GROUP BY source.entidad, source.batch_id, source.cosecha_canonica, source.moneda_original, source.moneda_resuelta
ORDER BY source.entidad, source.batch_id, source.cosecha_canonica, source.moneda_original;

-- 7. Conciliación Wandoo por documento/cosecha sin exponer DNI. Las diferencias
-- deben ser cero antes de cualquier publicación y WAN1 debe cubrir las operaciones.
SELECT COUNT(*) AS flg_cliente_calculado,
       SUM(document_group.flg_cuenta) AS flg_cuenta_calculado,
       SUM(document_group.cons_deuda_k) AS cons_deuda_k_calculada,
       SUM(document_group.cons_deuda_total) AS cons_deuda_total_calculada,
       SUM(document_group.cons_intereses) AS cons_intereses_calculada,
       COUNT(*) - 13042 AS diferencia_flg_cliente,
       SUM(document_group.flg_cuenta) - 13044 AS diferencia_flg_cuenta,
       SUM(document_group.cons_deuda_k) - CAST(6615373.31 AS DECIMAL(18,2)) AS diferencia_capital,
       SUM(document_group.cons_deuda_total) - CAST(6615373.31 AS DECIMAL(18,2)) AS diferencia_deuda_total,
       SUM(document_group.cons_intereses) - CAST(0.00 AS DECIMAL(18,2)) AS diferencia_componentes_no_capital,
       SUM(document_group.operaciones_con_wan1) AS operaciones_con_wan1,
       SUM(document_group.operaciones_sin_wan1) AS operaciones_sin_wan1
FROM (
    SELECT operation_row.documento_cliente, COUNT(*) AS flg_cuenta,
           SUM(operation_row.saldo_capital) AS cons_deuda_k,
           SUM(operation_row.deuda_total) AS cons_deuda_total,
           SUM(operation_row.deuda_total - operation_row.saldo_capital) AS cons_intereses,
           SUM(operation_row.identificador_origen LIKE 'WAN1:%') AS operaciones_con_wan1,
           SUM(operation_row.identificador_origen IS NULL OR operation_row.identificador_origen NOT LIKE 'WAN1:%') AS operaciones_sin_wan1
    FROM kp_silver.cartera_operaciones AS operation_row
    WHERE operation_row.entidad = 'WANDOO'
      AND operation_row.batch_id = 29
      AND operation_row.cosecha = 'WANDOO_1'
    GROUP BY operation_row.documento_cliente
) AS document_group;
