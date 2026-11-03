#!/bin/sh
# 回滚/恢复：停容器 → 校验备份完整性 → 覆盖数据库 → 起服务 → 等待健康 → 校验 /healthz。
# 用法：scripts/rollback.sh [备份文件]（缺省取 data/backup 下最新的 ocr-gateway-*.db）
set -eu

SCRIPTS_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPTS_DIR/common.sh"

usage() {
    cat <<'EOF'
用法：scripts/rollback.sh [备份文件]
  备份文件  要恢复的备份（data/backup/ocr-gateway-*.db）；缺省取最新一个。
流程：docker compose down → 校验备份 → 覆盖 data/ocr-gateway.db → up → 等待健康 → 校验 /healthz。
EOF
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
esac

cd "$REPO_ROOT"
check_docker
require_cmd sqlite3 "安装示例（Debian/Ubuntu）：sudo apt-get install -y sqlite3"

backup_file=${1:-}
if [ -z "$backup_file" ]; then
    backup_file=$(ls -1t "$BACKUP_DIR"/ocr-gateway-*.db 2>/dev/null | head -n 1)
fi
if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
    die "备份不存在：${backup_file:-（$BACKUP_DIR 下没有备份文件）}"
fi

log "校验备份完整性 ..."
integrity=$(sqlite3 "$backup_file" 'PRAGMA integrity_check;' 2>&1) || true
if [ "$integrity" != "ok" ]; then
    die "备份完整性校验失败：$backup_file（integrity_check=${integrity:-无法读取}）"
fi
log "备份完整：$backup_file"

log "docker compose down（优雅停，等待 stop_grace_period）..."
docker compose down

log "恢复数据库：$backup_file → $DB_FILE"
rm -f "$DB_FILE-wal" "$DB_FILE-shm"
cp "$backup_file" "$DB_FILE"

log "docker compose up -d ..."
docker compose up -d

wait_healthy 120
verify_healthz

log "回滚完成。备份来源：$backup_file"
