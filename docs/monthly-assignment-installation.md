# Instalación controlada de la fundación de asignación mensual

Este procedimiento prepara las trece tablas de Fase 1. No publica una
asignación, no modifica Bronze/Silver ni altera los procesos de importación
existentes. La instalación solo puede comenzar después de autorización expresa
y de ejecutar el preflight de lectura.

## Artefactos y cuentas

Copiar únicamente estos archivos al servidor, preservando sus SHA-256:

- `database/sql/059_create_monthly_assignment_foundation.sql`
- `database/sql/061_monthly_assignment_installation_preflight_read_only.sql`
- `database/sql/062_verify_monthly_assignment_foundation_read_only.sql`

La Fase A utiliza una cuenta distinta, restringida a `SELECT` sobre
`kp_control`, `kp_silver` e `information_schema`. La Fase B requiere una cuenta
temporal de despliegue con `CREATE`, `ALTER`, `INDEX`, `REFERENCES`, `INSERT` y
`SELECT` únicamente en `kp_control` y `kp_gold`. No usar la cuenta de Laravel,
la de ETL ni una cuenta administradora cotidiana.

No guardar contraseñas en comandos ni en el repositorio. Usar un archivo de
opciones de MySQL protegido por el DBA.

## Fase A: preflight de solo lectura

Desde el VPS, tras copiar el archivo a una ruta protegida:

```bash
mysql --defaults-extra-file=/ruta-protegida/kpdm-assignment-ro.cnf \
  --batch --raw --show-warnings \
  < /ruta-protegida/061_monthly_assignment_installation_preflight_read_only.sql \
  | tee /ruta-protegida/logs/monthly-assignment-preflight-$(date -u +%Y%m%dT%H%M%SZ).tsv
```

No continuar si ocurre cualquiera de estas condiciones:

1. La consulta 2 devuelve una de las 13 tablas propuestas.
2. Las tres tablas fuente requeridas no son InnoDB o faltan columnas usadas por
   el diagnóstico.
3. Los batches 7, 14, 21, 26 y 29 no son `CARTERA / COMPLETADO`, o batch 44 no
   es `PERSONAS / BASE_PERSONAS / COMPLETADO`, publicado, con `FULL_REPLACE` o
   `SCOPE_REPLACE`.
4. Confianza tiene una cosecha fuera del catálogo o `CONFIANZA_1`.
5. Wandoo no coincide con 13,044 operaciones, 13,042 documentos, capital y
   deuda de `6615373.31`, componentes no capital `0.00` y trazabilidad WAN1.
6. Hay duplicados cuya causa empresarial no ha sido revisada.

La salida de las consultas 7, 8 y 10 no expone DNI ni nombres. Puede convertirse
manualmente en el snapshot agregado que consume el preflight Python; esa
herramienta no se conecta a MySQL por sí sola.

## Respaldo y control de artefactos

Antes de DDL, un DBA debe tomar y verificar un respaldo lógico de los esquemas
destino y de sus metadatos:

```bash
mysqldump --defaults-extra-file=/ruta-protegida/kpdm-assignment-ddl.cnf \
  --single-transaction --routines --events --triggers \
  kp_control kp_gold \
  > /ruta-protegida/backups/kpdm-control-gold-before-monthly-assignment.sql

sha256sum /ruta-protegida/backups/kpdm-control-gold-before-monthly-assignment.sql
sha256sum /ruta-protegida/059_create_monthly_assignment_foundation.sql \
          /ruta-protegida/062_verify_monthly_assignment_foundation_read_only.sql
```

El respaldo no sustituye el preflight. Registrar en el cambio aprobado los tres
hashes, versión MySQL y salida de las consultas de Fase A.

## Fase B: instalación estricta

SQL 059 crea ocho tablas en `kp_control` y cinco en `kp_gold`. No usa
`CREATE TABLE IF NOT EXISTS` ni `INSERT IGNORE`: cualquier objeto o catálogo
preexistente hace fallar la instalación y requiere investigación.

Ejecutar dentro de una ventana autorizada, sin usar `--force`:

```bash
mysql --defaults-extra-file=/ruta-protegida/kpdm-assignment-ddl.cnf \
  --batch --raw --show-warnings \
  < /ruta-protegida/059_create_monthly_assignment_foundation.sql \
  | tee /ruta-protegida/logs/monthly-assignment-install-$(date -u +%Y%m%dT%H%M%SZ).tsv
```

El orden interno es deliberado:

1. Catálogos y control de periodos.
2. Selección de batches por periodo.
3. Generaciones Gold.
4. Clientes, trazabilidad de operaciones, conciliación y anomalías.
5. FK del puntero activo después de crear generaciones.
6. Seed de catálogos en una transacción independiente del DDL.

La única generación `PUBLISHED` se protege mediante un índice único sobre la
columna generada `official_periodo`; el puntero `active_generation_id` usa una
FK compuesta con el mismo periodo. Dos triggers impiden que el puntero señale
una generación no publicada o que una generación activa deje de estar
`PUBLISHED`. El intercambio debe hacerse, dentro de una sola transacción, en
este orden: liberar puntero, marcar la previa `SUPERSEDED`, publicar la nueva y
asignar el nuevo puntero. Generaciones `DRAFT`, `FAILED` y `SUPERSEDED` se
conservan como historial.

## Fase C: verificación posterior

```bash
mysql --defaults-extra-file=/ruta-protegida/kpdm-assignment-ro.cnf \
  --batch --raw --show-warnings \
  < /ruta-protegida/062_verify_monthly_assignment_foundation_read_only.sql \
  | tee /ruta-protegida/logs/monthly-assignment-postinstall-$(date -u +%Y%m%dT%H%M%SZ).tsv
```

Debe confirmar:

- `installed_table_count = 13` y `installation_status = PASS`.
- FKs, índice `uq_asignacion_generacion_official_periodo` y los dos triggers
  de integridad de generación activa.
- Cero filas Gold mensuales; instalar estructura no publica datos.
- 30 cosechas, 25 zonas, 11 aliases Confianza y una política de moneda.
- `CONFIANZA_5 / FONDO II`.
- `WANDOO / WANDOO_1 / PEN / is_active = 1`.
- Ningún alias activo para `CONFIANZA_1`.

## Recuperación de fallo parcial

DDL en MySQL confirma implícitamente. Un `ROLLBACK` no deshace un `CREATE TABLE`.
Ante un error:

1. Detenerse; no reejecutar SQL 059.
2. Ejecutar SQL 061 y archivar su salida para inventariar los objetos creados.
3. Verificar con SQL 062 si el seed llegó a ejecutarse y si existe cualquier fila
   Gold mensual.
4. Si no hay generaciones ni datos de asignación, un DBA puede aprobar la
   eliminación explícita de las tablas parciales en orden inverso a sus FKs y
   restaurar el respaldo si corresponde. Esa eliminación no forma parte de SQL
   059 y requiere una autorización separada.
5. Si existe cualquier generación, cliente u operación mensual, no eliminar
   tablas: preservar evidencia, restaurar únicamente con el plan aprobado y
   abrir incidencia.

No continuar hacia consolidación `202610` hasta que Fase C sea satisfactoria y
la revisión humana autorice la siguiente fase.
