#!/usr/bin/env bash
set -euo pipefail

# Build/publish helper for DouyinLiveRecorder Docker image.
# 借鉴 tg-file-monitor/scripts/docker_release.sh，适配本项目的版本号形式（main.py 里 version = "vX.Y"）。
# Examples:
#   ./scripts/docker_release.sh --image y1nf0x/douyinliverecorder --tag v0.42 --push
#   ./scripts/docker_release.sh --image y1nf0x/douyinliverecorder --push --platform linux/amd64
#   ./scripts/docker_release.sh --image y1nf0x/douyinliverecorder --save

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

IMAGE_REPO=""
IMAGE_TAG=""
PLATFORM=""
DO_PUSH="0"
DO_SAVE="0"
AUTO_BUMP_ON_DUP="1"
REMOTE_CACHE="1"
CACHE_REF=""

usage() {
  cat <<'EOF'
Usage:
  docker_release.sh --image <repo/name> [--tag <version>] [options]

Required:
  --image <repo/name>   Docker image repo, e.g. y1nf0x/douyinliverecorder
  --tag <version>       Image tag, e.g. v0.42 (optional; default from main.py 的 version)

Options:
  --platform <platform> Build platform, e.g. linux/amd64
  --push                Push image to registry（buildx --push，带 registry 构建缓存）
  --save                Export image tar.gz to dist/
  --cache-ref <ref>     Registry cache ref (default: <image>:buildcache)
  --no-cache            Disable registry build cache
  --allow-duplicate-tag Allow using an existing tag without auto-bump
  -h, --help            Show this help

Notes:
  - Always tags both <tag> and latest.
  - 若 tag 已存在（git tag 或 registry），默认自动递增小版本号。
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] command not found: $1"
    exit 1
  fi
}

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

detect_version() {
  local version_file="$ROOT_DIR/main.py"
  local line v
  line="$(grep -E '^version[[:space:]]*=' "$version_file" | head -n 1 || true)"
  [[ -z "$line" ]] && return 1
  v="$(echo "$line" | sed -E 's/^[^"]*"([^"]+)".*$/\1/')"
  [[ -n "$v" && "$v" != "$line" ]] && { echo "$v"; return 0; }
  return 1
}

set_version() {
  local target_version="$1"
  python3 - "$ROOT_DIR/main.py" "$target_version" <<'PY'
import re, sys
from pathlib import Path
path, target = Path(sys.argv[1]), sys.argv[2]
text = path.read_text(encoding="utf-8")
updated, count = re.subn(r'^version\s*=\s*"[^"]*"', f'version = "{target}"', text, count=1, flags=re.M)
if count != 1:
    raise SystemExit("version assignment not found in main.py")
path.write_text(updated, encoding="utf-8")
PY
}

is_release_like() {
  # vX.Y 或 X.Y.Z 均可
  [[ "$1" =~ ^v?[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]
}

bump_version() {
  # v0.42 -> v0.43；0.4.19 -> 0.4.20
  local v="$1" prefix="" core major minor patch
  [[ "$v" == v* ]] && { prefix="v"; core="${v#v}"; } || core="$v"
  if [[ "$core" =~ ^([0-9]+)\.([0-9]+)$ ]]; then
    major="${BASH_REMATCH[1]}"; minor="${BASH_REMATCH[2]}"
    printf '%s%s.%0*d' "$prefix" "$major" "${#minor}" "$((10#$minor + 1))"
  elif [[ "$core" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    major="${BASH_REMATCH[1]}"; minor="${BASH_REMATCH[2]}"; patch="${BASH_REMATCH[3]}"
    printf '%s%s.%s.%0*d' "$prefix" "$major" "$minor" "${#patch}" "$((10#$patch + 1))"
  else
    return 1
  fi
}

local_tag_exists() {
  local tag="$1"
  git rev-parse --git-dir >/dev/null 2>&1 || return 1
  git rev-parse -q --verify "refs/tags/${tag}" >/dev/null 2>&1
}

remote_tag_exists() {
  docker buildx imagetools inspect "${1}:${2}" >/dev/null 2>&1
}

resolve_non_duplicate_tag() {
  local repo="$1" base="$2" resolved="$2" tries=0
  if [[ "$AUTO_BUMP_ON_DUP" != "1" ]] || ! is_release_like "$resolved"; then
    if local_tag_exists "$resolved" || remote_tag_exists "$repo" "$resolved"; then
      echo "[ERROR] tag '$resolved' already exists." >&2
      return 1
    fi
    echo "$resolved"; return 0
  fi
  while local_tag_exists "$resolved" || remote_tag_exists "$repo" "$resolved"; do
    tries=$((tries + 1))
    (( tries > 100 )) && { echo "[ERROR] no available tag after 100 bumps from $base" >&2; return 1; }
    resolved="$(bump_version "$resolved")" || return 1
  done
  [[ "$resolved" != "$base" ]] && log "Tag '$base' already exists, auto-bumped to '$resolved'" >&2
  echo "$resolved"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)   IMAGE_REPO="${2:-}"; shift 2 ;;
    --tag)     IMAGE_TAG="${2:-}"; shift 2 ;;
    --platform) PLATFORM="${2:-}"; shift 2 ;;
    --push)    DO_PUSH="1"; shift ;;
    --save)    DO_SAVE="1"; shift ;;
    --cache-ref) CACHE_REF="${2:-}"; shift 2 ;;
    --no-cache) REMOTE_CACHE="0"; shift ;;
    --allow-duplicate-tag) AUTO_BUMP_ON_DUP="0"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[ERROR] unknown argument: $1"; usage; exit 1 ;;
  esac
done

[[ -z "$IMAGE_REPO" ]] && { echo "[ERROR] --image is required"; usage; exit 1; }
if [[ -z "$IMAGE_TAG" ]]; then
  IMAGE_TAG="$(detect_version || true)"
  [[ -n "$IMAGE_TAG" ]] && log "Auto-detected version from main.py: $IMAGE_TAG" \
    || { echo "[ERROR] --tag is required (and version not found in main.py)"; exit 1; }
fi

require_cmd docker
require_cmd git
require_cmd python3
mkdir -p "$DIST_DIR"

IMAGE_TAG="$(resolve_non_duplicate_tag "$IMAGE_REPO" "$IMAGE_TAG")"

CURRENT_VERSION="$(detect_version || true)"
if [[ "$CURRENT_VERSION" != "$IMAGE_TAG" ]]; then
  set_version "$IMAGE_TAG"
  log "Synced main.py version: ${CURRENT_VERSION:-unknown} -> $IMAGE_TAG"
fi

TAG_IMAGE="$IMAGE_REPO:$IMAGE_TAG"
LATEST_IMAGE="$IMAGE_REPO:latest"
[[ -z "$CACHE_REF" ]] && CACHE_REF="$IMAGE_REPO:buildcache"

log "Repository: $ROOT_DIR"
log "Build image: $TAG_IMAGE (also: $LATEST_IMAGE)"

if [[ "$DO_PUSH" == "1" ]]; then
  docker buildx version >/dev/null 2>&1 || { echo "[ERROR] docker buildx is required for --push mode"; exit 1; }
  build_args=(buildx build "$ROOT_DIR" -f "$ROOT_DIR/Dockerfile" -t "$TAG_IMAGE" -t "$LATEST_IMAGE" --push)
  [[ -n "$PLATFORM" ]] && build_args+=(--platform "$PLATFORM")
  if [[ "$REMOTE_CACHE" == "1" ]]; then
    build_args+=(--cache-from "type=registry,ref=$CACHE_REF" --cache-to "type=registry,ref=$CACHE_REF,mode=max")
    log "Registry cache: $CACHE_REF"
  fi
  log "Running: docker ${build_args[*]}"
  docker "${build_args[@]}"
  log "Push completed"
else
  build_args=(build "$ROOT_DIR" -f "$ROOT_DIR/Dockerfile" -t "$TAG_IMAGE" -t "$LATEST_IMAGE")
  [[ -n "$PLATFORM" ]] && build_args+=(--platform "$PLATFORM")
  log "Running: docker ${build_args[*]}"
  docker "${build_args[@]}"
  log "Local build completed"
fi

if [[ "$DO_SAVE" == "1" ]]; then
  [[ "$DO_PUSH" == "1" ]] && { log "--push mode: pulling $TAG_IMAGE for export"; docker pull "$TAG_IMAGE"; }
  ts="$(date +%Y%m%d_%H%M%S)"
  out_tgz="$DIST_DIR/$(basename "$IMAGE_REPO")-${IMAGE_TAG}-${ts}.tar.gz"
  log "Saving image to: $out_tgz"
  docker save "$TAG_IMAGE" | gzip > "$out_tgz"
  log "Export completed: $out_tgz"
fi

log "Done"
