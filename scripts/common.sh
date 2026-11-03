# 公共库：被 backup.sh / deploy.sh / rollback.sh source。
# 提供：仓库根定位、依赖检查、健康等待与 /healthz 校验。
# 约定：脚本可从任意 cwd 以绝对路径或相对路径调用（cron 友好）；
# 调用后脚本自身会 cd 到仓库根，所有默认路径（data/...）相对仓库根。
# 可覆盖的环境变量：DB_FILE（默认 data/ocr-gateway.db）、BACKUP_DIR（默认 data/backup）。

SCRIPTS_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPTS_DIR/.." && pwd)

DB_FILE=${DB_FILE:-data/ocr-gateway.db}
BACKUP_DIR=${BACKUP_DIR:-data/backup}
CONTAINER_NAME=ocr-gateway

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '[%s] ERROR: %s\n' "$(date +%H:%M:%S)" "$*" >&2; exit 1; }

require_cmd() {
    cmd=$1
    hint=$2
    if ! command -v "$cmd" >/dev/null 2>&1; then
        die "缺少命令 '$cmd'。$hint"
    fi
}

check_docker() {
    require_cmd docker "需要 Docker（含 docker compose v2 插件）。"
    if ! docker compose version >/dev/null 2>&1; then
        die "docker compose（v2 插件）不可用。"
    fi
}

# 轮询容器健康状态直到 healthy（默认 120 秒），超时非零退出并提示排查命令。
wait_healthy() {
    timeout=${1:-120}
    log "等待容器健康（最长 ${timeout}s）..."
    i=0
    while [ "$i" -lt "$timeout" ]; do
        status=$(docker inspect --format '{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || true)
        if [ "$status" = "healthy" ]; then
            log "容器已 healthy（约 ${i}s）"
            return 0
        fi
        sleep 5
        i=$((i + 5))
    done
    die "容器在 ${timeout}s 内未达到 healthy。排查：docker compose ps && docker compose logs --tail 50"
}

# 读 .env 的 HOST_PORT（缺省 8000）并断言 /healthz 返回 200。
verify_healthz() {
    host_port=8000
    if [ -f "$REPO_ROOT/.env" ]; then
        port_line=$(sed -n 's/^HOST_PORT=//p' "$REPO_ROOT/.env" | head -n 1)
        if [ -n "$port_line" ]; then
            host_port=$port_line
        fi
    fi
    require_cmd curl "需要 curl 校验 /healthz。"
    log "校验 http://127.0.0.1:${host_port}/healthz ..."
    if ! curl -fsS --max-time 5 "http://127.0.0.1:${host_port}/healthz" >/dev/null; then
        die "/healthz 未返回 200（端口 ${host_port}）。排查：docker compose logs --tail 50"
    fi
    log "/healthz 200 OK"
}
