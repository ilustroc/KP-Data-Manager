# Generación manual de asignación mensual: sólo DRAFT

El comando `python -m src.monthly_assignment_generator` reutiliza el
consolidador de Fase 1. No contiene una opción para publicar, cerrar un periodo
ni actualizar `active_generation_id`. Sólo admite un diagnóstico (`dry-run`) o
la creación explícita, transaccional y recuperable de una generación `DRAFT`.

La primera ejecución prevista está limitada a Wandoo:

- periodo: `202610`;
- fecha de corte provisional: `2026-10-26`;
- entidad y cosecha: `WANDOO / WANDOO_1`;
- batch cartera: `29`;
- batch PERSONAS: `44`;
- política aprobada de moneda: `WANDOO_1 = PEN`.

## Protecciones aplicadas

Antes de escribir, el comando valida la fundación de tablas, ambos batches, el
catálogo de cosechas, la política Wandoo, la conciliación financiera, los
conteos de banderas y las referencias `WAN1:`. Para Wandoo, exige exactamente
13,044 operaciones, 13,042 clientes, capital y deuda total de `6615373.31`, y
componentes no capital de `0.00`.

La persistencia toma un bloqueo MySQL nombrado de alcance
`periodo + entidad + cosecha`, bloquea las filas de control relevantes y se
ejecuta como una única transacción. Inserta clientes, trazas, conciliación y
anomalías por lotes. Cualquier excepción realiza rollback. Un reintento del
mismo alcance queda bloqueado si ya existe un `DRAFT`; borradores de alcances
distintos del mismo periodo no se bloquean entre sí.

El proceso sólo consulta `kp_silver.cartera_operaciones` y
`kp_silver.search_personas`; nunca escribe Bronze ni Silver. Los atributos
demográficos se leen exclusivamente del batch PERSONAS indicado, mediante
`LEFT JOIN`, por lo que los faltantes permanecen `NULL`.

## Comandos

Ejecutar siempre desde `etl/`, con el mismo mecanismo seguro de configuración
ETL existente. No incluir contraseñas en la línea de comandos y no modificar
`.env`. Para una prueba local, configurar antes una base aislada con los datos
de prueba y las variables `ETL_DB_*` ya soportadas por el ETL.

Diagnóstico sin escrituras:

```bash
cd /var/www/kp-data-manager/etl
/ruta/al/venv/bin/python -m src.monthly_assignment_generator \
  --periodo 202610 --fecha-corte 2026-10-26 \
  --entidad WANDOO --cosecha WANDOO_1 \
  --batch 29 --batch-personas 44
```

Sólo después de revisar el JSON de dry-run y obtener autorización explícita,
crear el borrador:

```bash
cd /var/www/kp-data-manager/etl
/ruta/al/venv/bin/python -m src.monthly_assignment_generator \
  --periodo 202610 --fecha-corte 2026-10-26 \
  --entidad WANDOO --cosecha WANDOO_1 \
  --batch 29 --batch-personas 44 \
  --write-draft \
  --confirm-write-draft 202610:WANDOO:WANDOO_1:29
```

La confirmación liga la escritura a periodo, entidad, cosecha y batch. El
resultado JSON sólo contiene conteos, estado y el `generation_id`; no imprime
datos personales. Ninguno de los comandos publica una generación.

## Verificación posterior de DRAFT

Con el `generation_id` informado por el comando, ejecutar
`database/sql/063_verify_monthly_assignment_draft_read_only.sql` sustituyendo
`<GENERATION_ID>` por ese entero. Debe observarse:

- `estado = DRAFT`, `published_at = NULL` y el periodo sin
  `active_generation_id`;
- 13,042 clientes, `SUM(flg_cliente) = 13042` y
  `SUM(flg_cuenta) = 13044`;
- capital y deuda total `6615373.31`, componentes `0.00`;
- 13,044 trazas, todas con `WAN1:` y moneda resuelta `PEN`;
- filas de conciliación con diferencias cero y estado `COMPLETE`.

Las consultas de SQL 063 son exclusivamente `SELECT` y no incluyen DNI,
nombres, teléfonos ni direcciones.

## Reversión de un DRAFT aprobado para descarte

Una escritura que falle antes del commit se revierte automáticamente. Si una
generación DRAFT ya confirmada debe descartarse, no se borran sus clientes ni
trazas: se preserva la auditoría y se marca la generación `FAILED`. Ejecutar
esto sólo con autorización, usando una cuenta de escritura controlada y el ID
verificado con SQL 063:

```sql
START TRANSACTION;

SELECT generation_id, periodo, estado
FROM kp_gold.asignacion_mensual_generaciones
WHERE generation_id = <GENERATION_ID>
FOR UPDATE;

SELECT periodo, active_generation_id, closed_at
FROM kp_control.asignacion_periodos
WHERE periodo = <PERIODO>
FOR UPDATE;

UPDATE kp_gold.asignacion_mensual_generaciones
SET estado = 'FAILED',
    failure_message = 'DRAFT revertido manualmente con autorización',
    finished_at = UTC_TIMESTAMP()
WHERE generation_id = <GENERATION_ID>
  AND estado = 'DRAFT';

COMMIT;
```

Antes del `UPDATE`, confirmar que la generación es `DRAFT`, que el periodo no
está cerrado y que `active_generation_id` es `NULL`. Si cualquiera de esas
condiciones no se cumple, ejecutar `ROLLBACK` y abrir una incidencia. La
generación queda disponible para auditoría y un nuevo intento no duplica sus
filas porque genera un ID técnico nuevo.

## Alcance futuro

Las demás carteras usan las mismas reglas de consolidación: aliases explícitos
de Confianza, clasificación centralizada de FONDO I/FONDO II, conversión USD a
PEN únicamente con tasa aprobada, y deuda BBVA `NULL` cuando no exista un
contrato que permita determinarla. Ninguna tasa USD se inventa; una cobertura
incompleta bloquea el borrador.
