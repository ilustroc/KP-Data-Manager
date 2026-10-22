#!/usr/bin/env bash
set -euo pipefail

command -v docker >/dev/null || {
    echo "Docker es obligatorio para esta prueba aislada." >&2
    exit 2
}

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
etl_root="$(cd "${script_directory}/.." && pwd)"
mysql_image="${MYSQL_IMAGE:-mysql:8.0}"
container_name="kpdm-mysql-essalud-${RANDOM}-$$"
mysql_password="kpdm-test-${RANDOM}-$$"
python_binary="${PYTHON_BIN:-python3}"

cleanup() {
    docker rm -f "${container_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run --detach --rm \
    --name "${container_name}" \
    --publish 127.0.0.1::3306 \
    --env MYSQL_ROOT_PASSWORD="${mysql_password}" \
    --env MYSQL_DATABASE=kpdm_bootstrap \
    --env MYSQL_USER=kpdm_test \
    --env MYSQL_PASSWORD="${mysql_password}" \
    "${mysql_image}" \
    --default-authentication-plugin=mysql_native_password >/dev/null

for _ in $(seq 1 90); do
    if docker exec --env MYSQL_PWD="${mysql_password}" "${container_name}" \
        mysql --protocol=TCP --host=127.0.0.1 --port=3306 --user=kpdm_test --database=kpdm_bootstrap --execute="SELECT 1" >/dev/null 2>&1; then
        docker exec --env MYSQL_PWD="${mysql_password}" "${container_name}" \
            mysql --protocol=TCP --host=127.0.0.1 --port=3306 --user=root --execute="GRANT ALL PRIVILEGES ON *.* TO 'kpdm_test'@'%'; FLUSH PRIVILEGES;"
        published_port="$(docker port "${container_name}" 3306/tcp | tail -n 1 | sed 's/.*://')"
        cd "${etl_root}"
        KPDM_RUN_MYSQL_INTEGRATION=1 \
        KPDM_MYSQL_HOST=127.0.0.1 \
        KPDM_MYSQL_PORT="${published_port}" \
        KPDM_MYSQL_USER=kpdm_test \
        KPDM_MYSQL_PASSWORD="${mysql_password}" \
        "${python_binary}" -m pytest -m mysql_integration tests/test_search_essalud_mysql_integration.py
        exit 0
    fi
    sleep 1
done

echo "MySQL no estuvo disponible dentro del plazo de la prueba." >&2
exit 1
