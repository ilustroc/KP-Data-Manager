-- DM-F6: grants manuales; no ejecutar automáticamente.
GRANT SELECT, INSERT ON `kp_silver`.`search_familiares` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE ON `kp_gold`.`search_familiares` TO 'kp_data_manager_etl'@'127.0.0.1';
GRANT SELECT ON `kp_gold`.`search_familiares` TO 'kp_search_reader'@'127.0.0.1';
