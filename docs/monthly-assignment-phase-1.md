# Fase 1: asignación mensual consolidada por cosecha

## Auditoría de la arquitectura existente

- `kp_silver.cartera_operaciones` es el contrato común de las cinco carteras:
  tiene `entidad`, `cosecha`, `documento_cliente`, importes `DECIMAL(15,2)`,
  moneda, fechas, `batch_id` y `source_raw_id`. El cargador inserta Bronze y
  Silver dentro de la misma transacción de chunk y correlaciona la fila Silver
  con su raw Bronze.
- Las tablas de detalle de BBVA, Caja Arequipa, Compartamos, Confianza y
  Wandoo siguen siendo necesarias para auditar campos específicos. Esta fase no
  las actualiza ni las usa para reemplazar los importes ya homologados en la
  tabla común.
- `kp_control.import_batch` conserva estado y metadatos de lote. Las columnas
  SEARCH `dataset_code`, `source_code`, `refresh_mode` y `published_at` hacen
  posible identificar una sola publicación PERSONAS; Gold SEARCH no es una
  fuente segura para esta decisión porque puede representar cargas parciales.
- Los índices existentes separan `cosecha`, `batch_id` y documento/entidad. El
  índice candidato `(batch_id, cosecha, documento_cliente)` se ajusta a la
  lectura de batches explícitamente aprobados antes de agrupar, pero no forma
  parte del SQL de esta fase: requiere revisión en réplica con
  `INFORMATION_SCHEMA` y `EXPLAIN` antes de un DDL separado.
- BBVA publica `saldo_capital`, `interes` y `mora`, pero `deuda_total = NULL`.
  No existe evidencia de que esos tres campos representen la deuda contractual
  completa; la asignación solariza el capital cuando puede, pero mantiene deuda
  total e intereses comerciales en `NULL`.
- Wandoo publica saldo deudor como capital y deuda total, pero su moneda Silver
  es `NULL`/`SIN_MONEDA`. La decisión de negocio comunicada para esta fase es
  que Wandoo está expresado en soles. No se infiere desde Silver: el seed
  protegido registra exclusivamente `WANDOO / WANDOO_1 / PEN`, activo, con la
  evidencia `confirmación funcional del negocio del 2026-10-26`. No afecta
  otras cosechas Wandoo actuales o futuras.

### Hallazgos reportados que requieren auditoría de réplica

Los siguientes hechos proceden de la consulta de solo lectura informada para
esta fase; no se repitió ninguna consulta contra producción:

- BBVA batch 7 mezcla PEN/USD y tiene `deuda_total = NULL`.
- Caja Arequipa batch 14 mezcla PEN/USD en `CAJAAQP2`; las demás cosechas
  reportadas están en PEN.
- Compartamos batch 21 reporta sus tres cosechas en PEN.
- Confianza batch 26 mezcla PEN/USD y puede reportar valores de cosecha con
  espacios. Los aliases históricos propuestos son `CONFIANZA 2` a
  `CONFIANZA 12`, cada uno hacia su código con guion bajo equivalente; requieren
  contraste con el inventario preliminar, no una sustitución global.
- Wandoo batch 29 tiene 13,044 operaciones y 13,042 documentos, con moneda
  `NULL`/`SIN_MONEDA` almacenada. Para `WANDOO_1`, la política PEN confirmada
  permite solarizar; el control de conciliación debe verificar los totales
  observados antes de cualquier publicación.

## Alcance y fuentes de verdad

Esta fase construye una fotografía mensual a partir de operaciones de cartera
Silver seleccionadas explícitamente. La unidad empresarial es
`cosecha + documento_cliente`; el periodo mensual es un metadato separado. Una
misma persona en dos cosechas produce dos filas y una persona con varias
operaciones dentro de una cosecha produce una sola fila.

`kp_silver.cartera_operaciones`, sus detalles por cartera y la fila Bronze
correlacionada por `batch_id` y `source_raw_id` son la fuente de verdad para
operaciones, importes, titular, cosecha, departamento y fechas. SEARCH no se
usa para decidir qué cliente entra ni para sustituir datos financieros. Solo
aporta `fecha_nacimiento`, `sexo` y `estado_civil` desde **un único** batch de
`kp_silver.search_personas`.

El contrato empresarial de salida tiene exactamente estos veinte campos:

```text
cadena, fecha_compra, documento_cliente, titular, flg_cliente, flg_cuenta,
tipo_monto, anio_cast, dpto, zona, ran_cap, fecha_nacimiento, sexo,
estado_civil, origen, entidad, cosecha, cons_deuda_k, cons_intereses,
cons_deuda_total
```

Los IDs de generación, periodo, batch y trazas se guardan fuera de este
contrato, en las tablas de control y trazabilidad propuestas por
`database/sql/059_create_monthly_assignment_foundation.sql`.

## Catálogos y datos incompletos

El script 059 es la única lista centralizada de las 30 cosechas y los 25
departamentos. Sus entidades son los códigos reales de los perfiles Silver:
`BBVA`, `CAJA_AREQUIPA`, `COMPARTAMOS`, `CONFIANZA` y `WANDOO`.

`SEMBRANDO` se conserva con `fecha_compra = NULL` y `entidad = NULL`: todavía
no existe un código de entidad Silver aprobado para esa cartera. Por seguridad
no se inventa uno; una operación SEMBRANDO queda como incidencia
`harvest_without_entity` hasta que se apruebe el contrato de origen.

Antes de la primera generación debe revisarse además la codificación histórica
de Confianza: el catálogo de negocio aprobado usa `CONFIANZA`, mientras una
fixture del perfil representa `CONFIANZA_1`. Esta entrega no las equipara ni
renombra datos; cualquier valor Silver no presente literalmente en el catálogo
se bloquea como `unknown_harvest` hasta documentar y aprobar la equivalencia.

La normalización de departamento solo se aplica a la búsqueda de zona:
mayúsculas, espacios repetidos y tildes se normalizan. El valor Bronze/Silver
no se modifica. Un valor vacío, contradictorio o fuera del catálogo deja
`zona = NULL` e informa una incidencia.

## Selección segura de cartera vigente

No es válido sumar todos los batches históricos de una cosecha. Antes de una
generación, el operador debe registrar exactamente un batch de cartera por
`periodo + cosecha` en `kp_control.asignacion_periodo_cartera_batch`, con su
motivo. La tabla protege contra dos selecciones de la misma cosecha para el
mismo periodo. El servicio también bloquea una ejecución que reciba más de un
`batch_id` para una cosecha, para impedir duplicación silenciosa.

La política inicial es conservadora: se selecciona un batch solo después de
revisar que su carga está completada y que los diagnósticos siguientes no
encuentran duplicación/solapamiento no explicada. No se intenta elegir
automáticamente "el más reciente".

```sql
-- Inventario de cargas de cartera por entidad y cosecha.
SELECT
    operation.entidad,
    operation.cosecha,
    operation.batch_id,
    COUNT(*) AS operaciones,
    COUNT(DISTINCT operation.documento_cliente) AS documentos,
    MIN(batch.fecha_fin) AS batch_fecha_fin,
    MAX(batch.estado) AS estado_batch
FROM kp_silver.cartera_operaciones AS operation
JOIN kp_control.import_batch AS batch ON batch.batch_id = operation.batch_id
GROUP BY operation.entidad, operation.cosecha, operation.batch_id
ORDER BY operation.entidad, operation.cosecha, operation.batch_id;

-- Posibles solapamientos entre batches. La coincidencia se investiga usando
-- entidad, cosecha, documento, operación y la referencia WAN1 cuando exista;
-- nunca se elimina ni se deduplica automáticamente solo por DNI + operación.
SELECT
    current_row.entidad,
    current_row.cosecha,
    current_row.documento_cliente,
    current_row.operacion,
    current_row.identificador_origen,
    GROUP_CONCAT(DISTINCT current_row.batch_id ORDER BY current_row.batch_id) AS batches,
    COUNT(*) AS filas
FROM kp_silver.cartera_operaciones AS current_row
GROUP BY
    current_row.entidad,
    current_row.cosecha,
    current_row.documento_cliente,
    current_row.operacion,
    current_row.identificador_origen
HAVING COUNT(DISTINCT current_row.batch_id) > 1
ORDER BY current_row.entidad, current_row.cosecha, current_row.documento_cliente;
```

La segunda consulta es un diagnóstico, no una regla de deduplicación. En
particular, Wandoo puede conservar filas con el mismo DNI y número de préstamo;
la referencia `WAN1:` es trazable, no una clave empresarial única.

## Solarización y controles financieros

`MonthlyAssignmentConsolidator` agrupa solamente operaciones preseleccionadas
por `(cosecha, documento_cliente)`. Conserva ceros iniciales de documento y
cuenta todas las filas de operación: `flg_cliente = 1`,
`flg_cuenta = COUNT(*)`. No usa `DISTINCT operacion`.

Las tres columnas financieras del contrato se expresan únicamente en PEN. La
solarización ocurre por operación y antes de agrupar. Para PEN el factor es
`1`; para USD se selecciona el último tipo de cambio aprobado con fecha menor
o igual que `fecha_corte`. La propuesta de negocio es `SBS_VENTA` publicada a
través del BCRP (`PD04640PD`), pero esa política y su fuente deben ser
aprobadas antes de una publicación real. Esta fase no consulta ningún servicio
externo ni incorpora cotizaciones reales automáticamente.

Todos los cálculos usan `Decimal` y cada importe convertido se redondea a dos
decimales con `ROUND_HALF_UP` antes de sumar. Cuando capital y deuda total de
todas las operaciones están disponibles tras la conversión, usa:

```text
cons_deuda_k     = SUM(saldo_capital)
cons_deuda_total = SUM(deuda_total)
cons_intereses   = cons_deuda_total - cons_deuda_k
```

Una mezcla PEN/USD ya no es una anomalía en sí: cada operación se convierte y
recién se consolida. Si falta moneda confirmada o tipo de cambio, los tres
importes quedan `NULL`, la fila y sus contadores se conservan, y la publicación
queda bloqueada. Si la moneda/capital son válidos pero falta deuda total, se
conserva `cons_deuda_k` y se dejan `cons_deuda_total` y `cons_intereses` en
`NULL`, con una incidencia de cobertura; no se presenta una deuda parcial como
total completo.

No se emplea `fecha_compra` para convertir. Un tipo de cambio futuro nunca se
usa para suplir una fecha de corte sin cotización. La fecha, factor, clase y
fuente aplicados se congelan por operación en la generación; una actualización
posterior de `kp_control.tipos_cambio` no debe recalcular periodos cerrados.

`anio_cast` se publica solo si todas las operaciones del grupo tienen una fecha
de castigo y el año es único. `tipo_monto` y `ran_cap` se conservan `NULL` en
esta fase.

El ejemplo de Caja Arequipa se verifica por prueba con cuatro operaciones de
`CAJAAQP3` para el documento `30561135`: capital `26601.79`, deuda total
`57052.31`, componentes no capital `30450.52` y `flg_cuenta = 4`.

### Política de moneda y tipo de cambio

`kp_control.tipos_cambio` propone tasas `DECIMAL(18,8)` con clave de fecha,
par, clase y fuente. Una tasa nula, cero o ausente no equivale a `1`. La tabla
`kp_control.asignacion_politicas_moneda` permite confirmar moneda por entidad o
por cosecha, con evidencia; el alcance por cosecha tiene prioridad sobre el de
entidad. El script agrega únicamente la política protegida
`WANDOO_1 / PEN` confirmada el 2026-10-26; la decisión no se extiende a otras
cosechas Wandoo.

Para Confianza, las equivalencias históricas propuestas son `CONFIANZA 2` a
`CONFIANZA 12` hacia `CONFIANZA_2` a `CONFIANZA_12`, respectivamente. Cada una
se registra como alias explícito y auditado por entidad; `CONFIANZA_5` conserva
la clasificación `FONDO II` del catálogo. El servicio no cambia Silver ni
reemplaza globalmente espacios por guiones bajos, evitando colisiones.

## Enriquecimiento SEARCH

La primera generación debe registrar el batch PERSONAS `44`, siempre que su
estado publicado siga siendo `COMPLETADO`, su fuente `BASE_PERSONAS` y su modo
sea `SCOPE_REPLACE` o `FULL_REPLACE`. La unión es un `LEFT JOIN` por documento
contra `kp_silver.search_personas` filtrado exclusivamente por ese `batch_id`.
Una ausencia —o un valor vacío individual— queda `NULL`; no se consulta el
batch 34, 31 ni otro batch como fallback.

Para periodos futuros, `PersonasBatchSelector` acepta solo una publicación con
`dataset_code = PERSONAS`, `source_code = BASE_PERSONAS`, estado
`COMPLETADO`, `published_at` no nulo y modo `FULL_REPLACE` o `SCOPE_REPLACE`.
Elige la mayor pareja `(published_at, batch_id)`. Una carga parcial publicada es
válida: mejora atributos, pero no determina inclusión en la asignación.

```sql
-- Batch PERSONAS único para la primera fotografía (lectura previa obligatoria).
SELECT batch_id, dataset_code, source_code, refresh_mode, estado, published_at, rows_published
FROM kp_control.import_batch
WHERE batch_id = 44
  AND dataset_code = 'PERSONAS'
  AND source_code = 'BASE_PERSONAS'
  AND estado = 'COMPLETADO'
  AND refresh_mode IN ('FULL_REPLACE', 'SCOPE_REPLACE')
  AND published_at IS NOT NULL;
```

## Conciliación previa a publicación

La publicación queda bloqueada si el reporte de conciliación no cuadra para
las cifras completas. La consulta se ejecuta contra una selección materializada
o una tabla temporal de batches explícitamente aprobados; sustituya los valores
indicados por filas de `asignacion_periodo_cartera_batch`, no por todos los
batches históricos.

```sql
-- Ejemplo de conciliación para un periodo ya registrado, sin alterar datos.
SELECT
    selected.periodo,
    operation.entidad,
    operation.cosecha,
    catalog.origen,
    COUNT(*) AS operaciones_seleccionadas,
    COUNT(DISTINCT operation.documento_cliente) AS documentos_distintos,
    SUM(operation.saldo_capital) AS capital_original,
    SUM(operation.deuda_total) AS deuda_total_original,
    SUM(operation.deuda_total - operation.saldo_capital) AS componentes_no_capital,
    SUM(operation.saldo_capital IS NULL OR operation.deuda_total IS NULL) AS importes_incompletos
FROM kp_control.asignacion_periodo_cartera_batch AS selected
JOIN kp_silver.cartera_operaciones AS operation
  ON operation.batch_id = selected.batch_id
 AND operation.cosecha = selected.cosecha
JOIN kp_control.cartera_cosechas AS catalog
  ON catalog.cosecha = selected.cosecha
WHERE selected.periodo = :periodo
GROUP BY selected.periodo, operation.entidad, operation.cosecha, catalog.origen
ORDER BY operation.entidad, operation.cosecha;
```

El reporte del servicio entrega el equivalente por entidad, cosecha y origen:
operaciones, operaciones excluidas, documentos, clientes consolidados,
capital/deuda originales y consolidados, componentes no capital y anomalías.
Las trazas en
`asignacion_mensual_operaciones` permiten llevar cada fila Gold a su
`operacion_id`, `batch_id` y `source_raw_id` y desde allí a Bronze.

### Conciliación financiera solarizada

La conciliación de la fase 1A se materializa por `generation_id`, entidad,
cosecha, batch y moneda de origen. Las filas `moneda_origen = ALL` son las
únicas que comparan directamente la suma convertida de operaciones con la
asignación consolidada: una fila a nivel USD o PEN no puede atribuirse por sí
sola a una fila de cliente que contiene ambas monedas. El estado es:

- `COMPLETE`: cobertura completa y diferencias calculables.
- `PARTIAL`: falta capital o deuda total, aunque existan importes válidos.
- `BLOCKED`: falta moneda confirmada o tasa aprobada; no se publican totales.

```sql
-- Reporte de revisión por periodo, batch y moneda de origen ya congelado.
SELECT
    generation.periodo,
    reconciliation.entidad,
    reconciliation.cosecha,
    reconciliation.batch_id,
    reconciliation.moneda_origen,
    reconciliation.client_count,
    reconciliation.operation_count,
    reconciliation.capital_original_pen,
    reconciliation.capital_original_usd,
    reconciliation.capital_convertido_pen,
    reconciliation.deuda_total_convertida_pen,
    reconciliation.componentes_no_capital_pen,
    reconciliation.operations_without_currency,
    reconciliation.operations_without_debt_total,
    reconciliation.operations_without_exchange_rate,
    reconciliation.assignment_capital_pen,
    reconciliation.assignment_debt_total_pen,
    reconciliation.difference_capital_pen,
    reconciliation.difference_debt_total_pen,
    reconciliation.status,
    reconciliation.warnings
FROM kp_gold.asignacion_mensual_conciliacion AS reconciliation
JOIN kp_gold.asignacion_mensual_generaciones AS generation
  ON generation.generation_id = reconciliation.generation_id
WHERE generation.periodo = :periodo
ORDER BY reconciliation.entidad, reconciliation.cosecha,
         reconciliation.batch_id, reconciliation.moneda_origen;
```

La traza de operación guarda el monto original como proyección congelada junto
con su referencia inmutable a Silver/Bronze. Esta duplicación es deliberada:
permite reproducir la conciliación histórica aun si el acceso operativo a
Silver cambia. No es una fuente de verdad alternativa ni autoriza actualizar
Bronze o Silver.

La fixture de conciliación automatizada usa un cliente `CAJAAQP3` con una
operación PEN de capital/deuda `100.00/120.00` y otra USD de `10.00/15.00`,
con factor aprobado `3.50000000`. El reporte entrega `100.00` de capital
original PEN, `10.00` de capital original USD, capital convertido `135.00`,
deuda convertida `172.50`, componentes no capital `37.50`, diferencias
`0.00/0.00` y estado `COMPLETE`. Es un dato sintético de prueba, no una tasa
real ni una conciliación de producción.

El script [060_assignment_202610_reconciliation_read_only.sql](../database/sql/060_assignment_202610_reconciliation_read_only.sql)
prepara una conciliación preliminar del periodo `202610` para los batches candidatos
BBVA 7, Caja Arequipa 14, Compartamos 21, Confianza 26, Wandoo 29 y PERSONAS
44. Es autónomo respecto de las tablas propuestas en 059: solo consulta
`kp_silver.cartera_operaciones` y `kp_silver.search_personas`, por lo que puede
revisarse antes de cualquier DDL. Solo devuelve agregados: no expone DNI,
teléfonos, direcciones ni nombres, y no contiene DDL/DML. No debe ejecutarse
hasta contar con autorización y un entorno de lectura aprobado. No fija ni aplica
una fecha de corte, y no es una fotografía oficial ni una publicación Gold.

## Generación oficial, publicación atómica y catálogos protegidos

Las generaciones de prueba viven en `kp_gold.asignacion_mensual_generaciones`
con estado `DRAFT`, `FAILED`, `PUBLISHED` o `SUPERSEDED`. La única generación
oficial se identifica por `kp_control.asignacion_periodos.active_generation_id`;
por eso pueden conservarse varias pruebas sin que una consulta mensual use una
por error. Un periodo cerrado no cambia dicho puntero.

La futura publicación debe usar una transacción que bloquee la fila de periodo:

1. Validar catálogo, batches, tasas, trazabilidad y conciliación mientras la
   generación sigue en `DRAFT`.
2. Escribir clientes, operaciones y conciliación de esa generación.
3. Marcar la generación como `PUBLISHED`, marcar la oficial anterior como
   `SUPERSEDED` y actualizar `active_generation_id` en la misma transacción.
4. Ante cualquier error, hacer rollback: el puntero oficial previo permanece
   intacto y la generación nueva puede marcarse `FAILED` para auditoría.

El registro local de pruebas reproduce esa semántica: repetir exactamente la
fotografía oficial devuelve la misma generación; una nueva prueba sustituye la
vigente solo al publicarse exitosamente; una falla de validación no toca la
vigente; cerrar el periodo lo vuelve inmutable.

La instalación estricta de 059 usa `INSERT`, no `INSERT IGNORE` ni
`ON DUPLICATE KEY UPDATE`. Una fecha de compra, origen, entidad o zona ya
existente bloquea el seed y exige investigación; nunca se sobrescribe ni se
oculta una discrepancia. El preflight debe ejecutar `audit_catalogs`, revisar
su resultado y recién entonces registrar una solicitud en
`kp_control.asignacion_catalogo_cambios` para aprobación explícita. Ninguna
corrección se aplica desde el seed.

`kp_control.asignacion_cosecha_aliases` exige una correspondencia uno a uno
por entidad y valor fuente. El seed propone explícitamente `CONFIANZA 2` a
`CONFIANZA 12`; el inventario de SQL 060 debe confirmar cada origen antes de
usar los aliases. Un origen con dos destinos, un destino fuera del catálogo o
una cosecha sin equivalencia queda como incidencia y se excluye: no se
normaliza automáticamente.

## Fotografía mensual e idempotencia

`asignacion_periodos` almacena periodo, corte, batch PERSONAS, totales y estado;
la generación Gold guarda la versión del algoritmo y sus incidencias. La clave
empresarial dentro de una generación es `(cosecha, documento_cliente)`, y la
restricción única técnica es `(generation_id, cosecha, documento_cliente)`.

Una regeneración con las mismas filas es idempotente. Cambiar un periodo abierto
requiere una acción explícita registrada; un periodo cerrado nunca se
sobrescribe. El refresco de `estado_civil` se limita por política al día 1 y a
un periodo abierto. Las fotografías cerradas siguen inmutables. No hay scheduler
ni cron habilitado en esta fase.

## Flujo manual propuesto

1. Validar catálogo e inventario de batches; investigar los solapamientos.
2. Registrar los batches aprobados para un periodo y una fecha de corte.
3. Validar el batch PERSONAS único (44 para la primera corrida).
4. Ejecutar el consolidado sobre esa selección, guardar trazas e incidencias.
5. Revisar que los totales consolidados coincidan con los originales completos.
6. Publicar en una transacción una nueva generación Gold solo después de la
   conciliación aprobada; marcar periodo como cerrado únicamente tras revisión.

Esta entrega no instala interfaz, scheduler ni un ejecutor que escriba las
tablas propuestas; tampoco ejecuta el SQL. Así, la primera publicación real
sigue siendo una decisión controlada y revisable.

## Pendientes antes de interfaz y exportación definitiva

1. Auditar en una copia segura los batches vigentes y las equivalencias reales
   de cosecha, especialmente Confianza y SEMBRANDO.
2. Aprobar el procedimiento de selección manual y la semántica de periodo
   abierto/cerrado antes de habilitar escrituras Gold.
3. Definir los intervalos comerciales de `tipo_monto` y `ran_cap`.
4. Definir qué moneda representa las carteras sin moneda informada y una regla
   de conversión autorizada si se pretende combinar monedas distintas.
5. Añadir el adaptador transaccional, interfaz de revisión y exportación Excel
   en una fase posterior, después de validar conciliaciones contra una réplica.
6. Aprobar la clase de tipo de cambio, fuente, responsable de carga manual y
   controles de vigencia de `PD04640PD`; hasta entonces no se insertan tasas.
7. Ejecutar la conciliación de solo lectura de Wandoo batch 29 y verificar
   13,044 operaciones, 13,042 documentos y la igualdad de capital/deuda antes
   de utilizar su política PEN en una generación provisional.
