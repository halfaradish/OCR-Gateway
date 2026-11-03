#!/bin/sh
# 发布新版本（在目标服务器上执行）：
#   git pull --ff-only → 预部署备份 → 回滚台账 → compose build → up → 等待健康 → 校验 /healthz。
# 任一步失败即非零退出，并给出回滚提示。
# 用法：scripts/deploy.sh [--skip-pull] [-h|--help]
set -eu

SCRIPTS_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$SCRIPTS_DIR/common.sh"

usage() {
    cat <<'EOF'
用法：scripts/deploy.sh [--skip-pull]
  --skip-pull   跳过 git pull --ff-only（无 git 远程的服务器）
流程：git pull → 预部署备份 → 追加回滚台账 → compose build → up → 等待健康 → 校验 /healthz。
EOF
}

skip_pull=false
for arg in "$@"; do
    case "$arg" in
        --skip-pull) skip_pull=true ;;
        -h|--help) usage; exit 0 ;;
        *) die "未知参数：$arg（支持 --skip-pull）" ;;
    esac
done

cd "$REPO_ROOT"
check_docker
require_cmd sqlite3 "安装示例（Debian/Ubuntu）：sudo apt-get install -y sqlite3"

# git preflight：只在已跟踪文件干净且处于 main 时发布。
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "不是 git 仓库：$REPO_ROOT"
fi
git diff --quiet || die "工作树有未提交改动，先提交后再发布。"
git diff --cached --quiet || die "暂存区有内容，先提交后再发布。"
branch=$(git symbolic-ref --short HEAD 2>/dev/null || true)
if [ "$branch" != "main" ]; then
    die "当前分支 '$branch' 不是 main，请先切回 main。"
fi

if [ "$skip_pull" = true ]; then
    log "跳过 git pull（--skip-pull）"
else
    log "git pull --ff-only ..."
    git pull --ff-only || die "git pull 失败（存在分叉？）。手动处理后重试。"
fi

log "预部署备份 ..."
backup_file=$(sh "$SCRIPTS_DIR/backup.sh")
if [ ! -f "$backup_file" ]; then
    die "预部署备份失败：backup.sh 未返回有效路径（'$backup_file'）。"
fi

sha=$(git rev-parse HEAD)
printf '%s %s %s\n' "$(date -Is)" "$sha" "$backup_file" >> "data/backup/deploy-log"
log "回滚台账已追加：data/backup/deploy-log（git=$sha）"

log "docker compose build ..."
docker compose build

log "docker compose up -d ..."
docker compose up -d

wait_healthy 120
verify_healthz

log "发布完成（git=$sha）"
log "如需回滚：scripts/rollback.sh $backup_file"
