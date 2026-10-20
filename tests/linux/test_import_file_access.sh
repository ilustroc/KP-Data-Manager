#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Esta prueba debe ejecutarse en Linux o en un contenedor Linux." >&2
    exit 2
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Esta prueba aislada necesita root para crear y retirar usuarios temporales." >&2
    exit 2
fi

for command in php useradd userdel groupadd groupdel runuser stat sha256sum; do
    command -v "${command}" >/dev/null || {
        echo "Falta el comando requerido: ${command}" >&2
        exit 2
    }
done

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
test_root="$(mktemp -d /tmp/kpdm-import-access.XXXXXX)"
chmod 0755 "${test_root}"
web_user="kpdmweb"
etl_user="kpdeploy"
outsider_user="kpdmoutsider"
shared_group="kpdm-imports"

cleanup() {
    rm -rf -- "${test_root}"
    userdel "${outsider_user}" >/dev/null 2>&1 || true
    userdel "${etl_user}" >/dev/null 2>&1 || true
    userdel "${web_user}" >/dev/null 2>&1 || true
    groupdel "${shared_group}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for user_name in "${web_user}" "${etl_user}" "${outsider_user}"; do
    if id "${user_name}" >/dev/null 2>&1; then
        echo "El usuario ${user_name} ya existe; usa un contenedor Linux desechable." >&2
        exit 2
    fi
done
if getent group "${shared_group}" >/dev/null 2>&1; then
    echo "El grupo ${shared_group} ya existe; usa un contenedor Linux desechable." >&2
    exit 2
fi

groupadd "${shared_group}"
useradd --no-create-home --shell /usr/sbin/nologin --groups "${shared_group}" "${web_user}"
useradd --no-create-home --shell /usr/sbin/nologin --groups "${shared_group}" "${etl_user}"
useradd --no-create-home --shell /usr/sbin/nologin "${outsider_user}"

import_root="${test_root}/storage/app/private/imports"
install -d -o "${web_user}" -g "${shared_group}" -m 2750 "${import_root}"

env_fixture="${test_root}/.env"
printf '%s\n' 'APP_KEY=permission-test-only' > "${env_fixture}"
chmod 0600 "${env_fixture}"
env_hash_before="$(sha256sum "${env_fixture}" | awk '{print $1}')"
env_mode_before="$(stat -c '%a' "${env_fixture}")"

generated_path="$({
    runuser -u "${web_user}" -- env \
        APP_ENV=testing \
        APP_DEBUG=true \
        APP_KEY='base64:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' \
        LOG_CHANNEL=stderr \
        KPDM_TEST_IMPORT_ROOT="${import_root}" \
        KPDM_TEST_ETL_USER="${etl_user}" \
        KPDM_TEST_SHARED_GROUP="${shared_group}" \
        php "${project_root}/tests/Support/run_import_file_access_check.php"
} | tail -n 1)"

[[ -f "${generated_path}" ]]
[[ "$(stat -c '%U' "${generated_path}")" == "${web_user}" ]]
[[ "$(stat -c '%G' "${generated_path}")" == "${shared_group}" ]]
[[ "$(stat -c '%a' "${generated_path}")" == "640" ]]

current_directory="$(dirname "${generated_path}")"
while [[ "${current_directory}" == "${import_root}" || "${current_directory}" == "${import_root}/"* ]]; do
    [[ "$(stat -c '%G' "${current_directory}")" == "${shared_group}" ]]
    [[ "$(stat -c '%a' "${current_directory}")" == "2750" ]]
    [[ "$(stat -c '%A' "${current_directory}" | cut -c7)" == "s" ]]
    [[ "${current_directory}" == "${import_root}" ]] && break
    current_directory="$(dirname "${current_directory}")"
done

runuser -u "${etl_user}" -- test -r "${generated_path}"
runuser -u "${etl_user}" -- grep -q '934043966' "${generated_path}"

if runuser -u "${outsider_user}" -- test -r "${generated_path}"; then
    echo "Un usuario ajeno pudo leer el archivo privado." >&2
    exit 1
fi

if runuser -u "${outsider_user}" -- test -x "${import_root}"; then
    echo "Un usuario ajeno pudo atravesar el directorio privado." >&2
    exit 1
fi

userdel "${etl_user}"
useradd --no-create-home --shell /usr/sbin/nologin "${etl_user}"
runuser -u "${web_user}" -- env \
    APP_ENV=testing \
    APP_DEBUG=true \
    APP_KEY='base64:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' \
    LOG_CHANNEL=stderr \
    KPDM_TEST_IMPORT_ROOT="${import_root}" \
    KPDM_TEST_ETL_USER="${etl_user}" \
    KPDM_TEST_SHARED_GROUP="${shared_group}" \
    KPDM_TEST_EXPECT_FAILURE=1 \
    php "${project_root}/tests/Support/run_import_file_access_check.php" \
    | grep -q 'no pertenece al grupo compartido'

[[ "$(sha256sum "${env_fixture}" | awk '{print $1}')" == "${env_hash_before}" ]]
[[ "$(stat -c '%a' "${env_fixture}")" == "${env_mode_before}" ]]

echo "OK: kpdmweb crea privado, kpdeploy lee, terceros no acceden y el preflight falla antes de encolar si falta membresía."
