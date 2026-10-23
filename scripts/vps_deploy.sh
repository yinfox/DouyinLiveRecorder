#!/usr/bin/env bash
set -euo pipefail

# Deploy helper: pull image on the VPS and (re)start via docker compose.
# 借鉴 tg-file-monitor/scripts/netcup_deploy.sh，适配本项目部署在 openclaw + dpanel 管理的 compose。
# Examples:
#   ./scripts/vps_deploy.sh                          # 默认 openclaw + latest
#   ./scripts/vps_deploy.sh --tag v0.42
#   ./scripts/vps_deploy.sh --host openclaw --image y1nf0x/douyinliverecorder --tag latest

SSH_HOST="openclaw"
IMAGE_REPO="y1nf0x/douyinliverecorder"
IMAGE_TAG="latest"
COMPOSE_DIR="/data/docker_app/dpanel/config/compose/vodrecord"
CONTAINER="vodrecord-app-1"

usage() {
  cat <<'EOF'
Usage:
  vps_deploy.sh [--host <ssh-alias>] [--image <repo/name>] [--tag <tag>] [--compose-dir <path>]

Defaults:
  --host        openclaw
  --image       y1nf0x/douyinliverecorder
  --tag         latest
  --compose-dir /data/docker_app/dpanel/config/compose/vodrecord
EOF
}

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)        SSH_HOST="${2:-}"; shift 2 ;;
    --image)       IMAGE_REPO="${2:-}"; shift 2 ;;
    --tag)         IMAGE_TAG="${2:-}"; shift 2 ;;
    --compose-dir) COMPOSE_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] unknown argument: $1"; usage; exit 1 ;;
  esac
done

log "Deploy ${IMAGE_REPO}:${IMAGE_TAG} -> ${SSH_HOST}:${COMPOSE_DIR}"

ssh "$SSH_HOST" bash -s <<EOF
set -euo pipefail
docker pull "${IMAGE_REPO}:${IMAGE_TAG}"
cd "${COMPOSE_DIR}"
docker compose up -d --force-recreate
sleep 8
docker logs --tail 10 "${CONTAINER}" 2>&1 | grep -E '版本号|WebUI' || docker logs --tail 10 "${CONTAINER}"
EOF

log "Deploy done"
