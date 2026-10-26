-- Verificación de una generación mensual DRAFT.
-- Compatible con MySQL 5.7.33 y MySQL 8.0.
-- Solo lectura: reemplazar <GENERATION_ID> por el entero generado y ejecutar
-- con una cuenta limitada a SELECT. No expone DNI, nombres ni otros PII.

SELECT generation_id, periodo, generator_version, batch_personas_id, fecha_corte,
       tipo_cambio_clase, estado, started_at, finished_at, published_at,
       superseded_at, rows_generated, operations_selected, anomaly_count
FROM kp_gold.asignacion_mensual_generaciones
WHERE generation_id = <GENERATION_ID>;

SELECT generation_id,
       COUNT(*) AS clientes,
       SUM(flg_cliente) AS suma_flg_cliente,
       SUM(flg_cuenta) AS suma_flg_cuenta,
       SUM(cons_deuda_k) AS capital_pen,
       SUM(cons_intereses) AS componentes_no_capital_pen,
       SUM(cons_deuda_total) AS deuda_total_pen
FROM kp_gold.asignacion_mensual_clientes
WHERE generation_id = <GENERATION_ID>
GROUP BY generation_id;

SELECT client.entidad, client.cosecha,
       COUNT(*) AS operaciones_trazadas,
       SUM(trace.identificador_origen REGEXP BINARY '^WAN1:[0-9a-f]{64}$') AS identificadores_wan1_validos,
       SUM(trace.moneda_resuelta = 'PEN') AS operaciones_resueltas_pen,
       SUM(trace.capital_convertido_pen) AS capital_trazado_pen,
       SUM(trace.deuda_total_convertida_pen) AS deuda_trazada_pen
FROM kp_gold.asignacion_mensual_clientes AS client
INNER JOIN kp_gold.asignacion_mensual_operaciones AS trace
  ON trace.assignment_client_id = client.assignment_client_id
WHERE client.generation_id = <GENERATION_ID>
GROUP BY client.entidad, client.cosecha;

SELECT batch_id, entidad, cosecha, moneda_origen, operation_count, client_count,
       capital_convertido_pen, deuda_total_convertida_pen,
       componentes_no_capital_pen, operations_without_currency,
       operations_without_debt_total, operations_without_exchange_rate,
       assignment_capital_pen, assignment_debt_total_pen,
       difference_capital_pen, difference_debt_total_pen, status
FROM kp_gold.asignacion_mensual_conciliacion
WHERE generation_id = <GENERATION_ID>
ORDER BY entidad, cosecha, moneda_origen;

SELECT code, COUNT(*) AS cantidad
FROM kp_gold.asignacion_mensual_anomalias
WHERE generation_id = <GENERATION_ID>
GROUP BY code
ORDER BY code;

SELECT period.periodo, period.fecha_corte, period.estado,
       period.active_generation_id, period.closed_at, period.batch_personas_id,
       generation.generation_id AS verified_generation_id, generation.estado AS generation_estado,
       generation.published_at AS generation_published_at
FROM kp_control.asignacion_periodos AS period
LEFT JOIN kp_gold.asignacion_mensual_generaciones AS generation
  ON generation.generation_id = <GENERATION_ID>
WHERE period.periodo = generation.periodo;
