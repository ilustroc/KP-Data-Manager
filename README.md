# KP Data Manager

Aplicación interna de KP INVEST para gobierno, consulta e importación de datos operativos. La Fase 1 incluye el bootstrap de Laravel, autenticación, roles y layout administrativo. Los módulos de pagos e importaciones se habilitarán en fases posteriores.

## Requisitos

- PHP 8.3.35 con `ctype`, `fileinfo`, `filter`, `hash`, `mbstring`, `openssl`, `pdo`, `pdo_mysql`, `session` y `tokenizer`.
- Composer 2 (`/usr/local/bin/composer83` en producción).
- Node.js/npm para compilar assets.
- MySQL Community Server 5.7.33.
- Nginx apuntando exclusivamente al directorio `public/`.

Laravel está fijado en `composer.lock`; Composer simula la plataforma PHP 8.3.35 para impedir una resolución incompatible con producción.

## Instalación local

```bash
composer install
cp .env.example .env
php artisan key:generate
npm install
npm run build
php artisan migrate
php artisan kpdm:user:create
php artisan test --compact
```

En el servidor se deben usar `/opt/php83/bin/php` y `/usr/local/bin/composer83`. No se debe cambiar el PHP 7 existente ni la configuración de WordPress.

## Base de datos

La conexión predeterminada es `mysql_control`. Existen conexiones independientes:

- `mysql_bronze`
- `mysql_silver`
- `mysql_control`
- `mysql_gold`

Todas reciben host, puerto y credenciales desde `.env`; los nombres de esquema también son configurables. La cuenta debe ser propia de la aplicación y de privilegio mínimo. No usar `root` ni `jesus_admin`.

Los scripts bajo `database/sql/` son propuestas versionadas pendientes. No forman parte de `php artisan migrate` y nunca se ejecutan automáticamente.

## Usuarios y roles

No hay registro público ni usuarios predeterminados. El primer usuario se crea de forma interactiva:

```bash
php artisan kpdm:user:create --name="Nombre" --email="correo@empresa.pe" --role=ADMIN
```

La contraseña se solicita de forma oculta para evitar que aparezca en el historial o en la lista de procesos. Roles disponibles: `ADMIN`, `OPERADOR` y `LECTURA`.

## Documentación

La arquitectura, revisión del snapshot MySQL y plan por fases están en `docs/ARCHITECTURE.md`. El snapshot de referencia está en `docs/database-schema.sql` y no debe ejecutarse como migración.
