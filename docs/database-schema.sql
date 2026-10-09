-- MySQL dump 10.13  Distrib 5.7.33, for Linux (x86_64)
--
-- Host: localhost    Database: kp_control
-- ------------------------------------------------------
-- Server version	5.7.33-0ubuntu0.16.04.1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `kp_control`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `kp_control` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;

USE `kp_control`;

--
-- Table structure for table `cache`
--

DROP TABLE IF EXISTS `cache`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cache` (
  `key` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `value` mediumtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `expiration` bigint(20) NOT NULL,
  PRIMARY KEY (`key`),
  KEY `cache_expiration_index` (`expiration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cache_locks`
--

DROP TABLE IF EXISTS `cache_locks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cache_locks` (
  `key` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `expiration` bigint(20) NOT NULL,
  PRIMARY KEY (`key`),
  KEY `cache_locks_expiration_index` (`expiration`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `failed_jobs`
--

DROP TABLE IF EXISTS `failed_jobs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `failed_jobs` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `uuid` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `connection` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `queue` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payload` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `exception` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `failed_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `failed_jobs_uuid_unique` (`uuid`),
  KEY `failed_jobs_connection_queue_failed_at_index` (`connection`,`queue`,`failed_at`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `import_batch`
--

DROP TABLE IF EXISTS `import_batch`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `import_batch` (
  `batch_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `tipo` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `entidad` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `perfil_version` varchar(20) CHARACTER SET ascii DEFAULT NULL,
  `origen` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `archivo` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `archivo_original` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `archivo_interno` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `archivo_ruta` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `archivo_extension` varchar(20) CHARACTER SET ascii DEFAULT NULL,
  `archivo_mime` varchar(150) CHARACTER SET ascii DEFAULT NULL,
  `archivo_tamano` bigint(20) unsigned DEFAULT NULL,
  `archivo_sha256` char(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  `fecha_inicio` datetime NOT NULL,
  `fecha_fin` datetime DEFAULT NULL,
  `estado` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `filas_archivo` bigint(20) unsigned DEFAULT '0',
  `filas_insertadas` bigint(20) unsigned DEFAULT '0',
  `filas_duplicadas` bigint(20) unsigned DEFAULT '0',
  `filas_error` bigint(20) unsigned DEFAULT '0',
  `usuario` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `mensaje_error` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`batch_id`),
  KEY `idx_tipo` (`tipo`),
  KEY `idx_estado` (`estado`),
  KEY `idx_fecha_inicio` (`fecha_inicio`),
  KEY `idx_import_batch_origen` (`origen`),
  KEY `idx_import_batch_usuario` (`usuario`),
  KEY `idx_import_batch_archivo_sha256` (`archivo_sha256`),
  KEY `idx_import_batch_tipo_entidad_perfil` (`tipo`,`entidad`,`perfil_version`),
  KEY `idx_import_batch_entidad` (`entidad`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `import_deletion_log`
--

DROP TABLE IF EXISTS `import_deletion_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `import_deletion_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `batch_id_original` bigint(20) unsigned NOT NULL,
  `tipo` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `entidad` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `origen` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `archivo_original` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `archivo_interno` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_hash` char(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  `filas_archivo` bigint(20) unsigned NOT NULL DEFAULT '0',
  `filas_insertadas` bigint(20) unsigned NOT NULL DEFAULT '0',
  `filas_error` bigint(20) unsigned NOT NULL DEFAULT '0',
  `deleted_by_user_id` bigint(20) unsigned NOT NULL,
  `deleted_by_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `deleted_at` datetime NOT NULL,
  `file_deleted` tinyint(1) NOT NULL DEFAULT '0',
  `warning` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_import_deletion_batch` (`batch_id_original`),
  KEY `idx_import_deletion_entity` (`entidad`),
  KEY `idx_import_deletion_user` (`deleted_by_user_id`),
  KEY `idx_import_deletion_date` (`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `import_error`
--

DROP TABLE IF EXISTS `import_error`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `import_error` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `batch_id` bigint(20) unsigned NOT NULL,
  `numero_fila` bigint(20) unsigned NOT NULL,
  `campo` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `valor` text COLLATE utf8mb4_unicode_ci,
  `error` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_import_error_batch_row` (`batch_id`,`numero_fila`),
  KEY `idx_import_error_numero_fila` (`numero_fila`),
  CONSTRAINT `fk_import_error_batch` FOREIGN KEY (`batch_id`) REFERENCES `import_batch` (`batch_id`)
) ENGINE=InnoDB AUTO_INCREMENT=99565 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `job_batches`
--

DROP TABLE IF EXISTS `job_batches`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `job_batches` (
  `id` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `total_jobs` int(11) NOT NULL,
  `pending_jobs` int(11) NOT NULL,
  `failed_jobs` int(11) NOT NULL,
  `failed_job_ids` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `options` mediumtext COLLATE utf8mb4_unicode_ci,
  `cancelled_at` int(11) DEFAULT NULL,
  `created_at` int(11) NOT NULL,
  `finished_at` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `jobs`
--

DROP TABLE IF EXISTS `jobs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `jobs` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `queue` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payload` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `attempts` smallint(5) unsigned NOT NULL,
  `reserved_at` int(10) unsigned DEFAULT NULL,
  `available_at` int(10) unsigned NOT NULL,
  `created_at` int(10) unsigned NOT NULL,
  PRIMARY KEY (`id`),
  KEY `jobs_queue_index` (`queue`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `migrations`
--

DROP TABLE IF EXISTS `migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `migrations` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `migration` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `batch` int(11) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `pago_documento_resolucion`
--

DROP TABLE IF EXISTS `pago_documento_resolucion`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `pago_documento_resolucion` (
  `id_resolucion` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `raw_pago_id` bigint(20) unsigned NOT NULL,
  `documento_anterior` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `documento_nuevo` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `motivo` varchar(260) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `usuario` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `fecha_modificacion` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `activo` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id_resolucion`),
  KEY `idx_raw_pago_id` (`raw_pago_id`),
  KEY `idx_documento_nuevo` (`documento_nuevo`),
  KEY `idx_fecha_modificacion` (`fecha_modificacion`),
  KEY `idx_pago_resolucion_raw_activo` (`raw_pago_id`,`activo`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `password_reset_tokens`
--

DROP TABLE IF EXISTS `password_reset_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `password_reset_tokens` (
  `email` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `token` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sessions`
--

DROP TABLE IF EXISTS `sessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `sessions` (
  `id` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` bigint(20) unsigned DEFAULT NULL,
  `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_agent` text COLLATE utf8mb4_unicode_ci,
  `payload` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_activity` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `sessions_user_id_index` (`user_id`),
  KEY `sessions_last_activity_index` (`last_activity`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `users` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email_verified_at` timestamp NULL DEFAULT NULL,
  `password` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'LECTURA',
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `remember_token` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `users_email_unique` (`email`),
  KEY `users_role_index` (`role`),
  KEY `users_is_active_index` (`is_active`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping routines for database 'kp_control'
--

--
-- Current Database: `kp_bronze`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `kp_bronze` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;

USE `kp_bronze`;

--
-- Table structure for table `raw_cartera_bbva`
--

DROP TABLE IF EXISTS `raw_cartera_bbva`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `raw_cartera_bbva` (
  `CODCENTRAL` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `CONTRATO` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `CLAVE` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DESJUDICIA` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DOCUMENTO` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `UGA` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TERRITORIO` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NOMBRE` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MONEDA` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Suma de Importes` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Suma de INTERES` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Suma de MORA` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `OFICINA` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NOMB_OF` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `FECHAVEN` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `PRODUCTO` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DESCPROD` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipodoc` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `numdoc` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `direccion` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `REFE` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `referencia1` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `referencia2` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ubicacion` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `codpostal` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ubigeo` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dpto` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `provincia` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `distrito` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipofono1` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `prefijo1` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fono1` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `extension1` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipofono2` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `prefijo2` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fono2` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `extension2` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipofono3` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `prefijo3` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fono3` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `extension3` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipofono4` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `prefijo4` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fono4` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `extension4` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipofono5` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `prefijo5` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fono5` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `extension5` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NOMB_ESTUD` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nomb_est_saehost` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `COSECHA` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `raw_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_row` bigint(20) unsigned NOT NULL,
  `source_file` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `row_hash` char(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `ingested_at` datetime NOT NULL,
  PRIMARY KEY (`raw_id`),
  KEY `idx_raw_cartera_bbva_batch_row` (`batch_id`,`source_row`),
  KEY `idx_raw_cartera_bbva_row_hash` (`row_hash`)
) ENGINE=InnoDB AUTO_INCREMENT=2724 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `raw_cartera_caja_arequipa`
--

DROP TABLE IF EXISTS `raw_cartera_caja_arequipa`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `raw_cartera_caja_arequipa` (
  `NRO_DOC_TIT` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `AGENCIA` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ANALISTA` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TITULAR` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `CUENTA` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `OPERACION` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIPO_CONTABLE` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIP_SBS` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MONEDA` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `SALDO_CAPITAL` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `FEC_ULT_PAG` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DIAS_ATRASO` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `CUO_PAG` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DIR_LEGAL` text COLLATE utf8mb4_unicode_ci,
  `REF_LEGAL` text COLLATE utf8mb4_unicode_ci,
  `DIS_LEGAL` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TEL_TIT` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DIR_GES` text COLLATE utf8mb4_unicode_ci,
  `REF_GES` text COLLATE utf8mb4_unicode_ci,
  `DIS_GES` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TEL_GES` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ACTIVIDAD` text COLLATE utf8mb4_unicode_ci,
  `DIR_NEG` text COLLATE utf8mb4_unicode_ci,
  `DIS_NEG` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NRO_AVALES` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NOM_AVAL` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DIR_AVAL` text COLLATE utf8mb4_unicode_ci,
  `REF_AVAL` text COLLATE utf8mb4_unicode_ci,
  `DIS_AVAL` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIP_DOC_TIT` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NRO_DOC_TIT_2` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Segunda ocurrencia de NRO_DOC_TIT en el encabezado fuente',
  `TIP_DOC_AVAL` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NRO_DOC_AVAL` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TEL_AVAL` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `COD_SBS` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `FEC_DES` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MTO_DES` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `INT_MORATORIO` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `INT_COMP` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ICV` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `SEGUROS` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `PENALIDAD` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `OTROS_RUBROS` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TOT_DEUDA` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `CAL_SBS` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `PROVISION` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `FEC_ING_JUD` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `FEC_ING_CAS` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `REFINANCIADO` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIP_GAR1` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MTO_GAR1` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIP_GAR2` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MTO_GAR2` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIP_GAR3` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MTO_GAR3` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIP_GAR4` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MTO_GAR4` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIP_GAR5` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MTO_GAR5` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TIP_GAR6` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MTO_GAR6` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `UBIGEO` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DEPARTAMENTO` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `PROVINCIA` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `DISTRITO` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `COSECHA` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `raw_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_row` bigint(20) unsigned NOT NULL,
  `source_file` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `row_hash` char(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `ingested_at` datetime NOT NULL,
  PRIMARY KEY (`raw_id`),
  KEY `idx_raw_cartera_caja_batch_row` (`batch_id`,`source_row`),
  KEY `idx_raw_cartera_caja_row_hash` (`row_hash`)
) ENGINE=InnoDB AUTO_INCREMENT=62563 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `raw_cartera_compartamos`
--

DROP TABLE IF EXISTS `raw_cartera_compartamos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `raw_cartera_compartamos` (
  `Ctacliente` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Operación` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Documento` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NomCliente` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `oficina Agencia` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Skapital` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `IntComp` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `IntMoratorio` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Deuda total` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Moneda` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `TipCambio` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `SKSoles` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Lote` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Empresa` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `FecCastigo` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `FecDesembolso` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Dias_Atraso` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `LinNeg` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NumDoc` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NomDistrito` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NomProvincia` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `NomDepartamento` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `FecNacimiento` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Direccion Cliente` text COLLATE utf8mb4_unicode_ci,
  `Direccion Negocio` text COLLATE utf8mb4_unicode_ci,
  `Telefono1` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Telefono2` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Telefono3` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Telefono4` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Cosecha` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `raw_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_row` bigint(20) unsigned NOT NULL,
  `source_file` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `row_hash` char(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  `ingested_at` datetime NOT NULL,
  PRIMARY KEY (`raw_id`),
  KEY `idx_raw_cartera_compartamos_batch_row` (`batch_id`,`source_row`),
  KEY `idx_raw_cartera_compartamos_row_hash` (`row_hash`)
) ENGINE=InnoDB AUTO_INCREMENT=315047 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `raw_pagos`
--

DROP TABLE IF EXISTS `raw_pagos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `raw_pagos` (
  `FECHA` date DEFAULT NULL,
  `DOCUMENTO` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `MONTO` decimal(15,2) DEFAULT NULL,
  `ACUMULADO` decimal(15,2) DEFAULT NULL,
  `RECAUDO` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `OPERACION` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `COMENTARIO` varchar(260) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `HORA` time DEFAULT NULL,
  `raw_id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `source_file` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `batch_id` bigint(20) unsigned DEFAULT NULL,
  `ingested_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `row_hash` char(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  PRIMARY KEY (`raw_id`),
  KEY `idx_raw_pagos_row_hash` (`row_hash`),
  KEY `idx_raw_pagos_batch_id` (`batch_id`)
) ENGINE=InnoDB AUTO_INCREMENT=570 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping routines for database 'kp_bronze'
--

--
-- Current Database: `kp_silver`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `kp_silver` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;

USE `kp_silver`;

--
-- Table structure for table `cartera_avales`
--

DROP TABLE IF EXISTS `cartera_avales`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cartera_avales` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `operacion_id` bigint(20) unsigned NOT NULL,
  `documento_cliente` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `entidad` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `orden` tinyint(3) unsigned NOT NULL,
  `nombre_aval` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo_documento` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `documento_aval` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `telefono` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `direccion` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `referencia` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `distrito` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cantidad_reportada` int(11) DEFAULT NULL,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_raw_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cartera_avales_operacion` (`operacion_id`),
  KEY `idx_cartera_avales_entidad_documento` (`entidad`,`documento_cliente`),
  KEY `idx_cartera_avales_documento_aval` (`documento_aval`),
  KEY `idx_cartera_avales_batch` (`batch_id`),
  KEY `idx_cartera_avales_source` (`source_raw_id`)
) ENGINE=InnoDB AUTO_INCREMENT=9694 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cartera_caja_arequipa_detalle`
--

DROP TABLE IF EXISTS `cartera_caja_arequipa_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cartera_caja_arequipa_detalle` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `operacion_id` bigint(20) unsigned NOT NULL,
  `documento_cliente` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `analista` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo_contable` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fecha_ultimo_pago` date DEFAULT NULL,
  `cuo_pag` int(11) DEFAULT NULL,
  `actividad` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nro_avales_reportado` int(11) DEFAULT NULL,
  `codigo_sbs` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `monto_desembolso` decimal(15,2) DEFAULT NULL,
  `icv` decimal(15,2) DEFAULT NULL,
  `seguros` decimal(15,2) DEFAULT NULL,
  `penalidad` decimal(15,2) DEFAULT NULL,
  `otros_rubros` decimal(15,2) DEFAULT NULL,
  `calificacion_sbs` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `provision` decimal(15,4) DEFAULT NULL,
  `fecha_ingreso_judicial` date DEFAULT NULL,
  `refinanciado` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_raw_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_caja_arequipa_detalle_operacion` (`operacion_id`),
  KEY `idx_caja_arequipa_detalle_documento` (`documento_cliente`),
  KEY `idx_caja_arequipa_detalle_batch` (`batch_id`),
  KEY `idx_caja_arequipa_detalle_source` (`source_raw_id`),
  KEY `idx_caja_arequipa_detalle_codigo_sbs` (`codigo_sbs`)
) ENGINE=InnoDB AUTO_INCREMENT=62563 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cartera_compartamos_detalle`
--

DROP TABLE IF EXISTS `cartera_compartamos_detalle`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cartera_compartamos_detalle` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `operacion_id` bigint(20) unsigned NOT NULL,
  `documento_cliente` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `documento_fuente` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tipo_cambio` decimal(18,6) DEFAULT NULL,
  `saldo_capital_soles` decimal(15,2) DEFAULT NULL,
  `lote` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `empresa` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `anio_desembolso` smallint(5) unsigned DEFAULT NULL,
  `fecha_nacimiento` date DEFAULT NULL,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_raw_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cartera_compartamos_detalle_operacion` (`operacion_id`),
  KEY `idx_cartera_compartamos_detalle_documento` (`documento_cliente`),
  KEY `idx_cartera_compartamos_detalle_batch` (`batch_id`),
  KEY `idx_cartera_compartamos_detalle_source` (`source_raw_id`)
) ENGINE=InnoDB AUTO_INCREMENT=315047 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cartera_contactos`
--

DROP TABLE IF EXISTS `cartera_contactos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cartera_contactos` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `operacion_id` bigint(20) unsigned NOT NULL,
  `documento_cliente` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `entidad` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `telefono` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tipo` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `prefijo` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `extension` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `orden` tinyint(3) unsigned NOT NULL,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_raw_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cartera_contactos_operacion` (`operacion_id`),
  KEY `idx_cartera_contactos_entidad_documento` (`entidad`,`documento_cliente`),
  KEY `idx_cartera_contactos_telefono` (`telefono`),
  KEY `idx_cartera_contactos_batch` (`batch_id`),
  KEY `idx_cartera_contactos_source` (`source_raw_id`)
) ENGINE=InnoDB AUTO_INCREMENT=431844 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cartera_direcciones`
--

DROP TABLE IF EXISTS `cartera_direcciones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cartera_direcciones` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `operacion_id` bigint(20) unsigned NOT NULL,
  `documento_cliente` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `entidad` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tipo_direccion` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `direccion` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `referencia` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `referencia1` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `referencia2` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ubicacion` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `codigo_postal` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ubigeo` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `departamento` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `provincia` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `distrito` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_raw_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cartera_direcciones_operacion` (`operacion_id`),
  KEY `idx_cartera_direcciones_entidad_documento` (`entidad`,`documento_cliente`),
  KEY `idx_cartera_direcciones_ubigeo` (`ubigeo`),
  KEY `idx_cartera_direcciones_departamento` (`departamento`),
  KEY `idx_cartera_direcciones_batch` (`batch_id`),
  KEY `idx_cartera_direcciones_source` (`source_raw_id`)
) ENGINE=InnoDB AUTO_INCREMENT=691267 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cartera_garantias`
--

DROP TABLE IF EXISTS `cartera_garantias`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cartera_garantias` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `operacion_id` bigint(20) unsigned NOT NULL,
  `documento_cliente` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `entidad` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `orden` tinyint(3) unsigned NOT NULL,
  `tipo_garantia` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `monto` decimal(15,2) DEFAULT NULL,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_raw_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cartera_garantias_operacion` (`operacion_id`),
  KEY `idx_cartera_garantias_entidad_documento` (`entidad`,`documento_cliente`),
  KEY `idx_cartera_garantias_tipo` (`tipo_garantia`),
  KEY `idx_cartera_garantias_batch` (`batch_id`),
  KEY `idx_cartera_garantias_source` (`source_raw_id`)
) ENGINE=InnoDB AUTO_INCREMENT=180338 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cartera_operaciones`
--

DROP TABLE IF EXISTS `cartera_operaciones`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `cartera_operaciones` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `entidad` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cosecha` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `documento_cliente` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tipo_documento` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cuenta` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `operacion` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `identificador_origen` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nombre_cliente` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `moneda` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `saldo_capital` decimal(15,2) DEFAULT NULL,
  `deuda_total` decimal(15,2) DEFAULT NULL,
  `interes` decimal(15,2) DEFAULT NULL,
  `mora` decimal(15,2) DEFAULT NULL,
  `fecha_castigo` date DEFAULT NULL,
  `fecha_desembolso` date DEFAULT NULL,
  `fecha_vencimiento` date DEFAULT NULL,
  `dias_atraso` int(11) DEFAULT NULL,
  `producto` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `descripcion_producto` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `agencia` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `oficina` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `territorio` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ubigeo` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `departamento` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `provincia` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `distrito` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `batch_id` bigint(20) unsigned NOT NULL,
  `source_raw_id` bigint(20) unsigned NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cartera_operaciones_entidad_documento` (`entidad`,`documento_cliente`),
  KEY `idx_cartera_operaciones_entidad_cuenta` (`entidad`,`cuenta`),
  KEY `idx_cartera_operaciones_entidad_operacion` (`entidad`,`operacion`),
  KEY `idx_cartera_operaciones_cosecha` (`cosecha`),
  KEY `idx_cartera_operaciones_batch` (`batch_id`),
  KEY `idx_cartera_operaciones_source` (`source_raw_id`),
  KEY `idx_cartera_operaciones_vencimiento` (`fecha_vencimiento`),
  KEY `idx_cartera_operaciones_departamento` (`departamento`)
) ENGINE=InnoDB AUTO_INCREMENT=380332 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Temporary table structure for view `v_pagos_actuales`
--

DROP TABLE IF EXISTS `v_pagos_actuales`;
/*!50001 DROP VIEW IF EXISTS `v_pagos_actuales`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE VIEW `v_pagos_actuales` AS SELECT
 1 AS `raw_id`,
 1 AS `FECHA`,
 1 AS `DOCUMENTO_ORIGINAL`,
 1 AS `DOCUMENTO`,
 1 AS `MONTO`,
 1 AS `ACUMULADO`,
 1 AS `RECAUDO`,
 1 AS `OPERACION`,
 1 AS `COMENTARIO`,
 1 AS `HORA`,
 1 AS `source_file`,
 1 AS `batch_id`,
 1 AS `ingested_at`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary table structure for view `v_pagos_sin_identificar`
--

DROP TABLE IF EXISTS `v_pagos_sin_identificar`;
/*!50001 DROP VIEW IF EXISTS `v_pagos_sin_identificar`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE VIEW `v_pagos_sin_identificar` AS SELECT
 1 AS `raw_id`,
 1 AS `FECHA`,
 1 AS `DOCUMENTO_ORIGINAL`,
 1 AS `DOCUMENTO`,
 1 AS `MONTO`,
 1 AS `ACUMULADO`,
 1 AS `RECAUDO`,
 1 AS `OPERACION`,
 1 AS `COMENTARIO`,
 1 AS `HORA`,
 1 AS `source_file`,
 1 AS `batch_id`,
 1 AS `ingested_at`*/;
SET character_set_client = @saved_cs_client;

--
-- Dumping routines for database 'kp_silver'
--

--
-- Current Database: `kp_gold`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `kp_gold` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;

USE `kp_gold`;

--
-- Temporary table structure for view `v_gestiones_macro_12m`
--

DROP TABLE IF EXISTS `v_gestiones_macro_12m`;
/*!50001 DROP VIEW IF EXISTS `v_gestiones_macro_12m`*/;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE VIEW `v_gestiones_macro_12m` AS SELECT
 1 AS `PERIODO`,
 1 AS `DIA`,
 1 AS `HORA`,
 1 AS `ASESOR`,
 1 AS `GESTIONES`*/;
SET character_set_client = @saved_cs_client;

--
-- Dumping routines for database 'kp_gold'
--

--
-- Current Database: `kp_control`
--

USE `kp_control`;

--
-- Current Database: `kp_bronze`
--

USE `kp_bronze`;

--
-- Current Database: `kp_silver`
--

USE `kp_silver`;

--
-- Final view structure for view `v_pagos_actuales`
--

/*!50001 DROP VIEW IF EXISTS `v_pagos_actuales`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`jesus_admin`@`127.0.0.1` SQL SECURITY INVOKER */
/*!50001 VIEW `v_pagos_actuales` AS select `P`.`raw_id` AS `raw_id`,`P`.`FECHA` AS `FECHA`,`P`.`DOCUMENTO` AS `DOCUMENTO_ORIGINAL`,(case when isnull(nullif(trim(coalesce(`R`.`documento_nuevo`,`P`.`DOCUMENTO`)),'')) then NULL when ((trim(coalesce(`R`.`documento_nuevo`,`P`.`DOCUMENTO`)) regexp '^[0-9]+$') and (char_length(trim(coalesce(`R`.`documento_nuevo`,`P`.`DOCUMENTO`))) < 8)) then lpad(trim(coalesce(`R`.`documento_nuevo`,`P`.`DOCUMENTO`)),8,'0') else trim(coalesce(`R`.`documento_nuevo`,`P`.`DOCUMENTO`)) end) AS `DOCUMENTO`,`P`.`MONTO` AS `MONTO`,`P`.`ACUMULADO` AS `ACUMULADO`,`P`.`RECAUDO` AS `RECAUDO`,`P`.`OPERACION` AS `OPERACION`,`P`.`COMENTARIO` AS `COMENTARIO`,`P`.`HORA` AS `HORA`,`P`.`source_file` AS `source_file`,`P`.`batch_id` AS `batch_id`,`P`.`ingested_at` AS `ingested_at` from (`kp_bronze`.`raw_pagos` `P` left join `kp_control`.`pago_documento_resolucion` `R` on(((`R`.`raw_pago_id` = `P`.`raw_id`) and (`R`.`activo` = 1)))) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_pagos_sin_identificar`
--

/*!50001 DROP VIEW IF EXISTS `v_pagos_sin_identificar`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`jesus_admin`@`127.0.0.1` SQL SECURITY INVOKER */
/*!50001 VIEW `v_pagos_sin_identificar` AS select `v_pagos_actuales`.`raw_id` AS `raw_id`,`v_pagos_actuales`.`FECHA` AS `FECHA`,`v_pagos_actuales`.`DOCUMENTO_ORIGINAL` AS `DOCUMENTO_ORIGINAL`,`v_pagos_actuales`.`DOCUMENTO` AS `DOCUMENTO`,`v_pagos_actuales`.`MONTO` AS `MONTO`,`v_pagos_actuales`.`ACUMULADO` AS `ACUMULADO`,`v_pagos_actuales`.`RECAUDO` AS `RECAUDO`,`v_pagos_actuales`.`OPERACION` AS `OPERACION`,`v_pagos_actuales`.`COMENTARIO` AS `COMENTARIO`,`v_pagos_actuales`.`HORA` AS `HORA`,`v_pagos_actuales`.`source_file` AS `source_file`,`v_pagos_actuales`.`batch_id` AS `batch_id`,`v_pagos_actuales`.`ingested_at` AS `ingested_at` from `kp_silver`.`v_pagos_actuales` where (isnull(`v_pagos_actuales`.`DOCUMENTO`) or (trim(`v_pagos_actuales`.`DOCUMENTO`) = '')) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Current Database: `kp_gold`
--

USE `kp_gold`;

--
-- Final view structure for view `v_gestiones_macro_12m`
--

/*!50001 DROP VIEW IF EXISTS `v_gestiones_macro_12m`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`jesus_admin`@`127.0.0.1` SQL SECURITY DEFINER */
/*!50001 VIEW `v_gestiones_macro_12m` AS select date_format(convert_tz(`kpinvest_konnexia`.`cob_gestiones`.`created_at`,'+00:00','-05:00'),'%Y%m') AS `PERIODO`,cast(convert_tz(`kpinvest_konnexia`.`cob_gestiones`.`created_at`,'+00:00','-05:00') as date) AS `DIA`,hour(convert_tz(`kpinvest_konnexia`.`cob_gestiones`.`created_at`,'+00:00','-05:00')) AS `HORA`,coalesce(nullif(trim(`kpinvest_konnexia`.`cob_gestiones`.`agente_nombre`),''),'SIN ASESOR') AS `ASESOR`,count(0) AS `GESTIONES` from `kpinvest_konnexia`.`cob_gestiones` where ((`kpinvest_konnexia`.`cob_gestiones`.`created_at` >= convert_tz((date_format(convert_tz(utc_timestamp(),'+00:00','-05:00'),'%Y-%m-01') - interval 12 month),'-05:00','+00:00')) and (`kpinvest_konnexia`.`cob_gestiones`.`created_at` < utc_timestamp())) group by date_format(convert_tz(`kpinvest_konnexia`.`cob_gestiones`.`created_at`,'+00:00','-05:00'),'%Y%m'),cast(convert_tz(`kpinvest_konnexia`.`cob_gestiones`.`created_at`,'+00:00','-05:00') as date),hour(convert_tz(`kpinvest_konnexia`.`cob_gestiones`.`created_at`,'+00:00','-05:00')),coalesce(nullif(trim(`kpinvest_konnexia`.`cob_gestiones`.`agente_nombre`),''),'SIN ASESOR') */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-09 20:27:07
