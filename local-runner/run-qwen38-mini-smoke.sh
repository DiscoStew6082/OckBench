#!/bin/zsh

set -u
set -o pipefail

script_dir=${0:A:h}
repo_root=${script_dir:h}

omlx_bin=${OMLX_BIN:-/Volumes/Envoy/projects/omlx-inference-lab/.venv/bin/omlx}
model_root=${QWEN38_MODEL_ROOT:-/Volumes/Envoy/models/omlx}
image_name=${OCKBENCH_IMAGE:-ockbench-local-native}
run_id=${OCKBENCH_RUN_ID:-qwen3.8-27b-oq8-mtp-omlx-mini-smoke}
artifact_root=${OCKBENCH_ARTIFACT_ROOT:-${repo_root}/artifacts/${run_id}}
model_id=Qwen3.8-27B-oQ8-mtp
server_pid=""

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    print -u2 "Required command is unavailable: $1"
    return 1
  fi
}

stop_server() {
  if [[ -n ${server_pid} ]] && kill -0 "${server_pid}" >/dev/null 2>&1; then
    kill "${server_pid}" >/dev/null 2>&1 || true
    wait "${server_pid}" >/dev/null 2>&1 || true
  fi
  server_pid=""
}

cleanup() {
  stop_server
}

trap cleanup EXIT
trap 'cleanup; exit 130' INT TERM

start_server() {
  local effort=$1
  local state_dir=${artifact_root}/runtime/${effort}
  local server_log=${artifact_root}/logs/omlx-${effort}.log
  local models_json=""

  if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    print -u2 "Port 8000 already has a listener; refusing to disturb an unrelated service."
    return 1
  fi

  mkdir -p "${state_dir}" "${artifact_root}/logs"
  cp "${script_dir}/omlx/model_settings.json" "${state_dir}/model_settings.json"

  "${omlx_bin}" serve \
    --model-dir "${model_root}" \
    --host 127.0.0.1 \
    --port 8000 \
    --base-path "${state_dir}" \
    --max-concurrent-requests 1 \
    --memory-guard safe \
    --no-cache \
    --sse-keepalive-mode chunk \
    >"${server_log}" 2>&1 &
  server_pid=$!

  for attempt in {1..180}; do
    if ! kill -0 "${server_pid}" >/dev/null 2>&1; then
      print -u2 "oMLX exited before readiness. See ${server_log}"
      return 1
    fi

    models_json=$(curl -fsS --max-time 3 http://127.0.0.1:8000/v1/models 2>/dev/null) || true
    if [[ -n ${models_json} ]] && print -r -- "${models_json}" | jq -e --arg id "${model_id}" \
      '.data | any(.id == $id)' >/dev/null 2>&1; then
      print "oMLX ${effort} service ready with exact model id ${model_id}."
      return 0
    fi
    sleep 2
  done

  print -u2 "oMLX did not become ready within six minutes. See ${server_log}"
  return 1
}

run_domain() {
  local effort=$1
  local domain=$2
  local config_file=qwen38-${domain}-mini-${effort}.yaml
  local container_name=ockbench-qwen38-mini-${effort}-${domain}

  mkdir -p \
    "${artifact_root}/cache" \
    "${artifact_root}/results/${effort}/${domain}" \
    "${artifact_root}/logs/${effort}/${domain}"

  docker run --rm \
    --name "${container_name}" \
    --read-only \
    --tmpfs /tmp:rw,size=512m,nosuid,nodev,noexec \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --pids-limit 64 \
    --memory 2g \
    --cpus 2 \
    --user "$(id -u):$(id -g)" \
    --mount "type=bind,source=${artifact_root},target=/artifacts" \
    --mount "type=bind,source=${script_dir}/configs,target=/local/configs,readonly" \
    "${image_name}" \
    --config "/local/configs/${config_file}" \
    --cache "/artifacts/cache/${effort}-${domain}.jsonl" \
    --output-dir "/artifacts/results/${effort}/${domain}" \
    --log-dir "/artifacts/logs/${effort}/${domain}"
}

for required_command in docker curl jq lsof git; do
  require_command "${required_command}" || exit 1
done

if [[ ! -x ${omlx_bin} ]]; then
  print -u2 "oMLX executable is unavailable: ${omlx_bin}"
  exit 1
fi

if [[ ! -d ${model_root}/Qwen/Qwen3.8-27B-oQ8-mtp ]]; then
  print -u2 "Expected model directory is unavailable: ${model_root}/Qwen/Qwen3.8-27B-oQ8-mtp"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  print -u2 "Docker Desktop is not ready. Start Docker Desktop, then rerun this command."
  exit 1
fi

mkdir -p "${artifact_root}"
source_revision=$(git -C "${repo_root}" rev-parse HEAD)

print "Building ${image_name} from OckBench revision ${source_revision}."
docker build \
  --build-arg "OCKBENCH_SOURCE_REVISION=${source_revision}" \
  --file "${script_dir}/Dockerfile" \
  --tag "${image_name}" \
  "${repo_root}" || exit 1

typeset -a failed_lanes

for effort in medium low; do
  print "Starting ${effort} reasoning smoke lane."
  start_server "${effort}" || exit 1

  for domain in science coding; do
    print "Running ${effort} reasoning on official ${domain} mini (10 problems)."
    if ! run_domain "${effort}" "${domain}"; then
      failed_lanes+=("${effort}/${domain}")
      print -u2 "${effort}/${domain} returned nonzero; retained artifacts and continuing."
    fi
  done

  stop_server
done

print "Smoke sequence complete. Artifacts: ${artifact_root}"
if (( ${#failed_lanes[@]} > 0 )); then
  print -u2 "Lanes returning nonzero: ${failed_lanes[*]}"
  exit 1
fi
