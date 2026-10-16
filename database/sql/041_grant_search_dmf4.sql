-- DM-F4: grants manuales; no ejecutar automáticamente.
GRANT SELECT, INSERT ON `kp_silver`.`search_correos` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT, INSERT ON `kp_silver`.`search_direcciones` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT, INSERT ON `kp_silver`.`search_vehiculos` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT, INSERT ON `kp_silver`.`search_propiedades` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE ON `kp_gold`.`search_correos` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE ON `kp_gold`.`search_direcciones` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE ON `kp_gold`.`search_vehiculos` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE ON `kp_gold`.`search_propiedades` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT ON `kp_gold`.`search_correos` TO 'kp_search_reader'@'127.0.0.1';
GRANT SELECT ON `kp_gold`.`search_direcciones` TO 'kp_search_reader'@'127.0.0.1';
GRANT SELECT ON `kp_gold`.`search_vehiculos` TO 'kp_search_reader'@'127.0.0.1';
GRANT SELECT ON `kp_gold`.`search_propiedades` TO 'kp_search_reader'@'127.0.0.1';
