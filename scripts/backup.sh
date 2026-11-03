#!/bin/sh
# 每日备份：联机备份 SQLite（WAL 安全，无需停容器），并按保留天数清理旧备份。
# 用法：scripts/backup.sh
# 环境变量：BACKUP_DIR（默认 data/backup）、BACKUP_RETENTION_DAYS（默认 7）、
#           DB_FILE（默认 data/ocr-gateway.db）。
set -eu

SCRIPTS_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPTS_DIR/common.sh"
cd "$REPO_ROOT"

require_cmd sqlite3 "安装示例（Debian/Ubuntu）：sudo apt-get install -y sqlite3"

BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-7}
case "$BACKUP_RETENTION_DAYS" in
    ''|*[!0-9]*) die "BACKUP_RETENTION_DAYS 必须是非负整数（当前：'$BACKUP_RETENTION_DAYS'）。" ;;
esac

if [ ! -f "$DB_FILE" ]; then
    die "数据库不存在：$DB_FILE（服务尚未首次启动？）"
fi

mkdir -p "$BACKUP_DIR"

backup_file="$BACKUP_DIR/ocr-gateway-$(date +%F-%H%M%S).db"
# .backup 的退出码恒为 0，需确认产物确实生成。
sqlite3 "$DB_FILE" ".backup '$backup_file'"
if [ ! -f "$backup_file" ]; then
    die "备份未生成：$backup_file"
fi
log "备份完成：$backup_file"

if [ "$BACKUP_RETENTION_DAYS" -gt 0 ]; then
    find "$BACKUP_DIR" -name 'ocr-gateway-*.db' -mtime +"$BACKUP_RETENTION_DAYS" -delete
    remaining=$(find "$BACKUP_DIR" -name 'ocr-gateway-*.db' | wc -l | tr -d ' ')
    log "已清理 ${BACKUP_RETENTION_DAYS} 天前的备份（现余 ${remaining} 个）"
fi

# stdout 仅输出机器可读的备份路径（deploy.sh 依赖；日志均走上游 stderr）。
printf '%s\n' "$backup_file"
