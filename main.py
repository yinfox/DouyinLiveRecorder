# -*- encoding: utf-8 -*-

"""
Author: Hmily
GitHub: https://github.com/ihmily
Date: 2023-07-17 23:52:05
Update: 2025-10-23 19:48:05
Copyright (c) 2023-2025 by Hmily, All Rights Reserved.
Function: Record live stream video.
"""
import asyncio
import os
import sys
import builtins
import subprocess
import signal
import threading
import time
import datetime
import json
import re
import shutil
import random
import uuid
from pathlib import Path
import urllib.request
from urllib.error import URLError, HTTPError
from typing import Any
import configparser
import httpx
from src import spider, stream
from src.proxy import ProxyDetector
from src.utils import logger
from src import utils
from src.webui import (
    RecorderWebUI,
    append_rooms,
    clean_room_group,
    detect_permission_site,
    delete_room,
    infer_room_group,
    normalize_url,
    parse_room_group_part,
    parse_room_owner_part,
    permission_site_name,
    patch_rooms,
    read_rooms,
    start_webui_server,
    user_has_record_permission,
)
from msg_push import (
    dingtalk, xizhi, tg_bot, send_email, bark, ntfy, pushplus
)
from ffmpeg_install import (
    check_ffmpeg, ffmpeg_path, current_env_path
)

version = "v0.41"
platforms = ("\n国内站点：抖音|快手|虎牙|斗鱼|YY|B站|小红书|bigo|blued|网易CC|千度热播|猫耳FM|Look|TwitCasting|百度|微博|"
             "酷狗|花椒|流星|Acfun|畅聊|映客|音播|知乎|嗨秀|VV星球|17Live|浪Live|漂漂|六间房|乐嗨|花猫|淘宝|京东|咪咕|连接|来秀"
             "\n海外站点：TikTok|SOOP|PandaTV|WinkTV|FlexTV|PopkonTV|TwitchTV|LiveMe|ShowRoom|CHZZK|Shopee|"
             "Youtube|Faceit|xHamsterLive|Picarto")

recording = set()
error_count = 0
pre_max_request = 10
max_request_lock = threading.Lock()
error_window = []
error_window_size = 10
error_threshold = 5
error_backoff_notice_at = 0.0
monitoring = 0
running_list = []
url_tuples_list = []
url_comments = []
text_no_repeat_url = []
create_var = locals()
first_start = True
exit_recording = False
need_update_line_list = []
first_run = True
not_record_list = []
program_start_time = datetime.datetime.now()
start_display_time = datetime.datetime.now()
global_proxy = False
recording_time_list = {}
script_path = os.path.split(os.path.realpath(sys.argv[0]))[0]
config_file = f'{script_path}/config/config.ini'
url_config_file = f'{script_path}/config/URL_config.ini'
user_config_file = f'{script_path}/config/users.json'
record_history_file = f'{script_path}/config/record_history.json'
avatar_cache_file = f'{script_path}/config/avatar_cache.json'
backup_dir = f'{script_path}/backup_config'
text_encoding = 'utf-8-sig'
rstr = r"[\/\\\:\*\？?\"\<\>\|&#.。,， ~！· ]"
default_path = f'{script_path}/downloads'
os.makedirs(default_path, exist_ok=True)
ASS_PLAY_RES_X = 1080
ASS_PLAY_RES_Y = 1920
DANMU_REGION_LEFT = 36
DANMU_REGION_RIGHT = 860
DANMU_REGION_TOP = 1180
DANMU_REGION_BOTTOM = ASS_PLAY_RES_Y
DANMU_REGION_RIGHT_MARGIN = ASS_PLAY_RES_X - DANMU_REGION_RIGHT
DANMU_REGION_VERTICAL_MARGIN = ASS_PLAY_RES_Y - DANMU_REGION_BOTTOM
DANMU_REGION_FADE_HEIGHT = 48
DANMU_SCROLL_DELAY_MS = 12
DANMU_SCROLL_DURATION_SECONDS = 10
DANMU_FONT_SIZE = 36
DANMU_FONT_NAME = "Noto Sans CJK SC"
DANMU_MAX_TEXT_CHARS = 56
DANMU_BOX_PADDING = 1
DANMU_BOX_COLOR = "&H70000000"
DOUYIN_EMOJI_TEXT_MAP = {
    "鼓掌": "👏",
    "捂脸": "🤦",
    "玫瑰": "🌹",
    "赞": "👍",
    "爱心": "❤️",
    "红心": "❤️",
    "比心": "🫶",
    "大笑": "😄",
    "笑哭": "😂",
    "呲牙": "😁",
    "偷笑": "🤭",
    "尬笑": "😅",
    "流泪": "😢",
    "泪奔": "😭",
    "可怜": "🥺",
    "害羞": "😊",
    "惊讶": "😮",
    "发怒": "😡",
    "生气": "😠",
    "亲亲": "😘",
    "拥抱": "🤗",
    "祈祷": "🙏",
    "感谢": "🙏",
    "握手": "🤝",
    "OK": "👌",
    "ok": "👌",
    "加油": "💪",
    "强": "💪",
    "火": "🔥",
    "礼物": "🎁",
    "红包": "🧧",
    "啤酒": "🍺",
    "666": "👍",
}
DOUYIN_EMOJI_TAG_PATTERN = re.compile(r"[\[【]([^\[\]【】]{1,16})[\]】]")
CONVERSION_PROCESSING_DIR_NAME = ".dlr_processing"
SUBTITLE_BURN_WAIT_TIMEOUT_SECONDS = 30
SUBTITLE_BURN_STABLE_SECONDS = 2
ROOM_FLAG_LABELS = {
    "字幕": "record_subtitle",
    "录字幕": "record_subtitle",
    "生成字幕": "record_subtitle",
    "录制字幕": "record_subtitle",
    "烧录": "burn_subtitle",
    "烧录字幕": "burn_subtitle",
    "字幕烧录": "burn_subtitle",
}
ROOM_OPTION_LABELS = {
    "巡检": "check_interval",
    "检测": "check_interval",
    "循环": "check_interval",
    "间隔": "check_interval",
    "巡检间隔": "check_interval",
    "检测间隔": "check_interval",
    "浮动": "check_jitter",
    "随机": "check_jitter",
    "随机浮动": "check_jitter",
    "优先级": "priority",
    "优先": "priority",
    "星级": "priority",
    "星标": "priority",
    "星": "priority",
}
ROOM_PRIORITY_PRESETS = {
    "★★★": (60, 30),
    "★★": (300, 120),
    "★": (600, 120),
    "重点": (60, 30),
    "高": (60, 30),
    "高频": (60, 30),
    "普通": (300, 120),
    "默认": (300, 120),
    "低": (600, 120),
    "低频": (600, 120),
}
ROOM_STAR_PRIORITY_ALIASES = {
    "3": "★★★",
    "三": "★★★",
    "三星": "★★★",
    "★★★": "★★★",
    "重点": "★★★",
    "高": "★★★",
    "高频": "★★★",
    "2": "★★",
    "二": "★★",
    "两": "★★",
    "二星": "★★",
    "两星": "★★",
    "★★": "★★",
    "普通": "★★",
    "默认": "★★",
    "1": "★",
    "一": "★",
    "一星": "★",
    "★": "★",
    "低": "★",
    "低频": "★",
}
YES_VALUES = {"是", "true", "1", "yes", "y", "on"}
NO_VALUES = {"否", "false", "0", "no", "n", "off"}
file_update_lock = threading.Lock()
mp4_convert_lock = threading.Lock()
mp4_converting_files: set[str] = set()
mp4_convert_semaphore_lock = threading.Lock()
mp4_convert_semaphore = threading.Semaphore(1)
mp4_convert_semaphore_limit = 1
active_record_output_lock = threading.RLock()
active_record_outputs: set[str] = set()
ts_conversion_scanner_started = False
ts_conversion_scanner_lock = threading.Lock()
tg_interaction_started = False
tg_interaction_lock = threading.Lock()
webui_status_lock = threading.RLock()
webui_room_status = {}
room_runtime_options: dict[str, dict[str, int | str | None]] = {}
record_history_lock = threading.RLock()
avatar_cache_lock = threading.RLock()
avatar_cache_data: dict | None = None
system_metrics_lock = threading.RLock()
system_cpu_last: tuple[int, int] | None = None
resource_alert_lock = threading.RLock()
resource_alert_last_check = 0.0
resource_alert_last_sent: dict[str, float] = {}
resource_alert_active: set[str] = set()
size_split_urls = set()
room_dispatch_lock = threading.RLock()
room_dispatch_event = threading.Event()
room_worker_threads: dict[str, threading.Thread] = {}
room_monitor_configs: dict[str, tuple] = {}
room_next_check_monotonic: dict[str, float] = {}
room_worker_states: dict[str, dict[str, Any]] = {}
room_dispatcher_started = False
room_dispatcher_lock = threading.Lock()
os_type = os.name
clear_command = "cls" if os_type == 'nt' else "clear"
color_obj = utils.Color()
os.environ['PATH'] = ffmpeg_path + os.pathsep + current_env_path
SIZE_SPLIT_RESULT = "size_split"
TS_CONVERSION_STABLE_SECONDS = 90
TS_CONVERSION_SCAN_SECONDS = 60
TG_INTERACTION_RETRY_SECONDS = 10
TG_INTERACTION_POLL_TIMEOUT_SECONDS = 25
DEFAULT_FFMPEG_THREADS = 1
DEFAULT_MP4_CONVERT_CONCURRENCY = 1
DEFAULT_DIRECT_DOWNLOAD_CHUNK_KB = 256
DEFAULT_CONFIG_RELOAD_INTERVAL_SECONDS = 30
DEFAULT_RECORD_PROCESS_CHECK_INTERVAL_SECONDS = 5
DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS = 60
DEFAULT_REQUEST_ADJUST_INTERVAL_SECONDS = 60
DEFAULT_LOOP_RANDOM_JITTER_SECONDS = 120
DEFAULT_RESOURCE_ALERT_CPU_PERCENT = 90.0
DEFAULT_RESOURCE_ALERT_MEMORY_PERCENT = 90.0
DEFAULT_RESOURCE_ALERT_DISK_PERCENT = 90.0
DEFAULT_RESOURCE_ALERT_CHECK_SECONDS = 60
DEFAULT_RESOURCE_ALERT_COOLDOWN_SECONDS = 1800

try:
    threading.stack_size(512 * 1024)
except (RuntimeError, ValueError):
    pass


def read_cpu_times() -> tuple[int, int] | None:
    try:
        with open("/proc/stat", "r", encoding="utf-8") as stat_file:
            first_line = stat_file.readline().strip()
    except OSError:
        return None
    parts = first_line.split()
    if not parts or parts[0] != "cpu":
        return None
    try:
        values = [int(value) for value in parts[1:]]
    except ValueError:
        return None
    if not values:
        return None
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return total, idle


def cpu_load_fallback_percent() -> float | None:
    try:
        load_avg = os.getloadavg()[0]
    except (AttributeError, OSError):
        return None
    cpu_count = os.cpu_count() or 1
    return round(max(0.0, min(100.0, load_avg / cpu_count * 100)), 1)


def system_cpu_percent() -> float | None:
    global system_cpu_last
    current = read_cpu_times()
    if not current:
        return cpu_load_fallback_percent()
    with system_metrics_lock:
        previous = system_cpu_last
        system_cpu_last = current
    if not previous:
        return cpu_load_fallback_percent()
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        return cpu_load_fallback_percent()
    used_percent = (1 - max(0, idle_delta) / total_delta) * 100
    return round(max(0.0, min(100.0, used_percent)), 1)


def memory_metrics() -> dict:
    meminfo = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as meminfo_file:
            for line in meminfo_file:
                key, _, value = line.partition(":")
                if not key or not value:
                    continue
                amount = value.strip().split()[0]
                if amount.isdigit():
                    meminfo[key] = int(amount) * 1024
    except OSError:
        pass

    total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable", 0)
    if total <= 0:
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            page_count = os.sysconf("SC_PHYS_PAGES")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            total = int(page_size * page_count)
            available = int(page_size * available_pages)
        except (AttributeError, OSError, ValueError):
            total = 0
            available = 0

    used = max(0, total - available)
    percent = round(used / total * 100, 1) if total else None
    return {
        "percent": percent,
        "used_gb": round(used / (1024 ** 3), 2) if total else None,
        "total_gb": round(total / (1024 ** 3), 2) if total else None,
    }


def existing_disk_path(path: str) -> str:
    path = os.path.abspath(path or default_path)
    while path and not os.path.exists(path):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path if path and os.path.exists(path) else default_path


def disk_metrics() -> dict:
    disk_path = existing_disk_path(str(globals().get("video_save_path", "") or default_path))
    try:
        usage = shutil.disk_usage(disk_path)
    except OSError:
        return {"path": disk_path, "percent": None, "free_gb": None, "total_gb": None}
    used_percent = round(usage.used / usage.total * 100, 1) if usage.total else None
    return {
        "path": disk_path,
        "percent": used_percent,
        "free_gb": round(usage.free / (1024 ** 3), 2),
        "total_gb": round(usage.total / (1024 ** 3), 2),
    }


def get_system_metrics() -> dict:
    return {
        "cpu": {"percent": system_cpu_percent()},
        "memory": memory_metrics(),
        "disk": disk_metrics(),
    }


def format_percent(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{number:.1f}%"


def format_gb(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    return f"{number:.2f}GB" if number < 10 else f"{number:.1f}GB"


def resource_alert_detail(metric_name: str, metric: dict, threshold: float) -> str:
    percent_text = format_percent(metric.get("percent"))
    threshold_text = format_percent(threshold)
    if metric_name == "memory":
        return (
            f"内存: {percent_text} >= {threshold_text} "
            f"(已用 {format_gb(metric.get('used_gb'))} / {format_gb(metric.get('total_gb'))})"
        )
    if metric_name == "disk":
        return (
            f"硬盘: {percent_text} >= {threshold_text} "
            f"(剩余 {format_gb(metric.get('free_gb'))} / {format_gb(metric.get('total_gb'))})"
        )
    return f"CPU: {percent_text} >= {threshold_text}"


def build_resource_alert_message(alerts: list[tuple[str, dict, float]]) -> str:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with webui_status_lock:
        recording_count = len(recording)
        monitoring_count = monitoring
    lines = [
        "系统资源告警",
        f"时间: {timestamp}",
        *[resource_alert_detail(name, metric, threshold) for name, metric, threshold in alerts],
        f"运行: 录制 {recording_count} / 监控 {monitoring_count}",
    ]
    disk_path = next((metric.get("path") for name, metric, _threshold in alerts if name == "disk" and metric.get("path")), "")
    if disk_path:
        lines.append(f"磁盘路径: {disk_path}")
    return "\n".join(lines)


def send_resource_alert_to_tg(content: str) -> None:
    if not str(globals().get("tg_token", "") or "").strip() or not str(globals().get("tg_chat_id", "") or "").strip():
        return
    try:
        result = tg_bot(tg_chat_id, tg_token, content)
        print(
            f'提示信息：已经将系统资源告警推送至你的TG, '
            f'成功{len(result["success"])}, 失败{len(result["error"])}'
        )
    except Exception as err:
        color_obj.print_colored(f"系统资源告警推送到TG失败: {err}", color_obj.RED)


def maybe_send_system_resource_alert() -> None:
    global resource_alert_last_check
    if not bool(globals().get("resource_alert_enabled", False)):
        return
    if not str(globals().get("tg_token", "") or "").strip() or not str(globals().get("tg_chat_id", "") or "").strip():
        return
    now = time.monotonic()
    check_seconds = int(globals().get("resource_alert_check_seconds", DEFAULT_RESOURCE_ALERT_CHECK_SECONDS) or DEFAULT_RESOURCE_ALERT_CHECK_SECONDS)
    with resource_alert_lock:
        if now - resource_alert_last_check < max(5, check_seconds):
            return
        resource_alert_last_check = now

    thresholds = {
        "cpu": float(globals().get("resource_alert_cpu_percent", DEFAULT_RESOURCE_ALERT_CPU_PERCENT) or 0),
        "memory": float(globals().get("resource_alert_memory_percent", DEFAULT_RESOURCE_ALERT_MEMORY_PERCENT) or 0),
        "disk": float(globals().get("resource_alert_disk_percent", DEFAULT_RESOURCE_ALERT_DISK_PERCENT) or 0),
    }
    metrics = get_system_metrics()
    cooldown_seconds = max(
        60,
        int(globals().get("resource_alert_cooldown_seconds", DEFAULT_RESOURCE_ALERT_COOLDOWN_SECONDS) or DEFAULT_RESOURCE_ALERT_COOLDOWN_SECONDS),
    )

    alerts: list[tuple[str, dict, float]] = []
    with resource_alert_lock:
        for name, threshold in thresholds.items():
            metric = metrics.get(name) or {}
            percent = metric.get("percent")
            try:
                percent_value = float(percent)
            except (TypeError, ValueError):
                resource_alert_active.discard(name)
                continue
            if threshold <= 0 or percent_value < threshold:
                resource_alert_active.discard(name)
                continue
            last_sent = resource_alert_last_sent.get(name, 0.0)
            if name not in resource_alert_active or now - last_sent >= cooldown_seconds:
                alerts.append((name, metric, threshold))
                resource_alert_active.add(name)
                resource_alert_last_sent[name] = now

    if alerts:
        send_resource_alert_to_tg(build_resource_alert_message(alerts))


def default_avatar_cache() -> dict:
    return {"version": 1, "by_url": {}, "by_name": {}}


def normalize_avatar_url(value: Any) -> str:
    url = str(value or "").strip()
    if url.startswith("//"):
        url = f"https:{url}"
    if not url.startswith(("http://", "https://")):
        return ""
    return url


def avatar_name_key(value: Any) -> str:
    name = str(value or "").strip()
    name = re.sub(r"^序号\s*\d+\s*", "", name)
    if "主播:" in name:
        name = name.split("主播:", 1)[1].strip()
    if "主播：" in name:
        name = name.split("主播：", 1)[1].strip()
    return name.lower()


def load_avatar_cache() -> dict:
    global avatar_cache_data
    with avatar_cache_lock:
        if avatar_cache_data is not None:
            return avatar_cache_data
        path = Path(avatar_cache_file)
        if not path.exists():
            avatar_cache_data = default_avatar_cache()
            return avatar_cache_data
        try:
            with path.open("r", encoding="utf-8") as file:
                cache = json.load(file)
        except (OSError, json.JSONDecodeError):
            cache = default_avatar_cache()
        if not isinstance(cache, dict):
            cache = default_avatar_cache()
        cache.setdefault("version", 1)
        if not isinstance(cache.get("by_url"), dict):
            cache["by_url"] = {}
        if not isinstance(cache.get("by_name"), dict):
            cache["by_name"] = {}
        avatar_cache_data = cache
        return avatar_cache_data


def save_avatar_cache(cache: dict) -> None:
    with avatar_cache_lock:
        path = Path(avatar_cache_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(cache, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)


def cache_anchor_avatar(record_url: str, anchor_name: str, avatar_url: str) -> str:
    avatar_url = normalize_avatar_url(avatar_url)
    if not avatar_url:
        return ""
    now = datetime.datetime.now().isoformat(timespec="seconds")
    url_key = str(record_url or "").strip()
    name_key = avatar_name_key(anchor_name)
    changed = False
    with avatar_cache_lock:
        cache = load_avatar_cache()
        if url_key:
            current = cache["by_url"].get(url_key)
            anchor_text = str(anchor_name or "")
            if not isinstance(current, dict) or \
                    normalize_avatar_url(current.get("avatar_url")) != avatar_url or \
                    str(current.get("anchor_name") or "") != anchor_text:
                cache["by_url"][url_key] = {
                    "avatar_url": avatar_url,
                    "anchor_name": anchor_text,
                    "updated_at": now,
                }
                changed = True
        if name_key:
            current = cache["by_name"].get(name_key)
            anchor_text = str(anchor_name or "")
            if not isinstance(current, dict) or \
                    normalize_avatar_url(current.get("avatar_url")) != avatar_url or \
                    str(current.get("anchor_name") or "") != anchor_text or \
                    str(current.get("url") or "") != url_key:
                cache["by_name"][name_key] = {
                    "avatar_url": avatar_url,
                    "anchor_name": anchor_text,
                    "url": url_key,
                    "updated_at": now,
                }
                changed = True
        if changed:
            save_avatar_cache(cache)
    return avatar_url


def cached_anchor_avatar(record_url: str = "", *names: str) -> str:
    cache = load_avatar_cache()
    url_key = str(record_url or "").strip()
    if url_key:
        item = cache.get("by_url", {}).get(url_key)
        if isinstance(item, dict):
            avatar_url = normalize_avatar_url(item.get("avatar_url"))
            if avatar_url:
                return avatar_url
    for name in names:
        name_key = avatar_name_key(name)
        if not name_key:
            continue
        item = cache.get("by_name", {}).get(name_key)
        if isinstance(item, dict):
            avatar_url = normalize_avatar_url(item.get("avatar_url"))
            if avatar_url:
                return avatar_url
    return ""


def update_webui_room_status(record_url: str, **updates) -> None:
    if not record_url:
        return
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with webui_status_lock:
        current_status = webui_room_status.setdefault(record_url, {
            "url": record_url,
            "status": "queued",
            "last_checked_at": now,
        })
        avatar_name = (
                updates.get("anchor_name")
                or updates.get("configured_name")
                or updates.get("record_name")
                or current_status.get("anchor_name")
                or current_status.get("configured_name")
                or current_status.get("record_name")
                or ""
        )
        avatar_url = normalize_avatar_url(updates.get("avatar_url"))
        if avatar_url:
            updates["avatar_url"] = cache_anchor_avatar(record_url, avatar_name, avatar_url)
        elif not current_status.get("avatar_url"):
            cached_avatar = cached_anchor_avatar(record_url, avatar_name)
            if cached_avatar:
                updates["avatar_url"] = cached_avatar
        elif avatar_name:
            cache_anchor_avatar(record_url, avatar_name, current_status.get("avatar_url", ""))
        current_status.update({
            key: value for key, value in updates.items()
            if value is not None and not (key == "avatar_url" and not value)
        })
        current_status["url"] = record_url
        current_status["last_checked_at"] = now


def update_room_runtime_options(
        record_url: str,
        check_interval: int | None,
        check_jitter: int | None,
        priority: str,
) -> None:
    if not record_url:
        return
    with webui_status_lock:
        room_runtime_options[record_url] = {
            "check_interval": check_interval,
            "check_jitter": check_jitter,
            "priority": priority or "",
        }


def get_room_runtime_timing(record_url: str) -> tuple[int | None, int | None]:
    with webui_status_lock:
        options = dict(room_runtime_options.get(record_url, {}))
    priority_interval, priority_jitter = room_timing_from_priority(str(options.get("priority") or ""))
    check_interval = options.get("check_interval") or priority_interval
    check_jitter = options.get("check_jitter")
    if check_jitter is None:
        check_jitter = priority_jitter
    return check_interval, check_jitter


def mark_recording_started(record_name: str, quality: str) -> datetime.datetime:
    start_record_time = datetime.datetime.now()
    with webui_status_lock:
        recording.add(record_name)
        recording_time_list[record_name] = [start_record_time, quality]
    return start_record_time


def mark_recording_stopped(record_name: str) -> None:
    with webui_status_lock:
        recording.discard(record_name)
        recording_time_list.pop(record_name, None)


def is_stop_requested(record_url: str) -> bool:
    with webui_status_lock:
        return exit_recording or record_url in url_comments


def parse_split_size_mb(value: Any, default_mb: float = 1024.0) -> float:
    try:
        size_mb = float(str(value).strip())
    except (TypeError, ValueError):
        return default_mb
    return size_mb if size_mb > 0 else default_mb


def parse_int_setting(value: Any, default_value: int, min_value: int = 1, max_value: int | None = None) -> int:
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        number = default_value
    number = max(min_value, number)
    if max_value is not None:
        number = min(max_value, number)
    return number


def parse_float_setting(
        value: Any,
        default_value: float,
        min_value: float = 0.0,
        max_value: float | None = None,
) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        number = default_value
    number = max(min_value, number)
    if max_value is not None:
        number = min(max_value, number)
    return number


def add_instant_error() -> None:
    global error_count
    with max_request_lock:
        error_count += 1


def apply_error_backoff_delay(delay_seconds: int) -> int:
    global error_backoff_notice_at
    with max_request_lock:
        should_backoff = error_count > 20
        now = time.monotonic()
        should_print = should_backoff and now - error_backoff_notice_at >= 60
        if should_print:
            error_backoff_notice_at = now

    if not should_backoff:
        return delay_seconds
    if should_print:
        color_obj.print_colored("\r瞬时错误太多,延迟加60秒", color_obj.YELLOW)
    return delay_seconds + 60


def ffmpeg_thread_args() -> list[str]:
    thread_count = parse_int_setting(globals().get("ffmpeg_threads", DEFAULT_FFMPEG_THREADS), DEFAULT_FFMPEG_THREADS)
    return ["-threads", str(thread_count)]


def mp4_movflags_args() -> list[str]:
    if globals().get("mp4_faststart", False):
        return ["-movflags", "+faststart"]
    return []


def config_sleep_seconds() -> int:
    return parse_int_setting(
        globals().get("config_reload_interval_seconds", DEFAULT_CONFIG_RELOAD_INTERVAL_SECONDS),
        DEFAULT_CONFIG_RELOAD_INTERVAL_SECONDS,
    )


def record_process_check_seconds() -> int:
    return parse_int_setting(
        globals().get("record_process_check_interval_seconds", DEFAULT_RECORD_PROCESS_CHECK_INTERVAL_SECONDS),
        DEFAULT_RECORD_PROCESS_CHECK_INTERVAL_SECONDS,
    )


def status_refresh_seconds() -> int:
    return parse_int_setting(
        globals().get("status_refresh_interval_seconds", DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS),
        DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS,
    )


def get_request_adjust_interval_seconds() -> int:
    return parse_int_setting(
        globals().get("request_adjust_interval_seconds", DEFAULT_REQUEST_ADJUST_INTERVAL_SECONDS),
        DEFAULT_REQUEST_ADJUST_INTERVAL_SECONDS,
    )


def loop_random_jitter_seconds() -> int:
    return parse_int_setting(
        globals().get("loop_jitter_seconds", DEFAULT_LOOP_RANDOM_JITTER_SECONDS),
        DEFAULT_LOOP_RANDOM_JITTER_SECONDS,
        min_value=0,
    )


def insert_before_input(command: list[str], *items: str) -> None:
    try:
        input_index = command.index("-i")
    except ValueError:
        input_index = len(command)
    command[input_index:input_index] = list(items)


def configure_mp4_convert_semaphore(limit: int) -> None:
    global mp4_convert_semaphore, mp4_convert_semaphore_limit
    limit = max(1, int(limit))
    with mp4_convert_semaphore_lock:
        if limit == mp4_convert_semaphore_limit:
            return
        mp4_convert_semaphore = threading.Semaphore(limit)
        mp4_convert_semaphore_limit = limit


def current_mp4_convert_semaphore() -> threading.Semaphore:
    with mp4_convert_semaphore_lock:
        return mp4_convert_semaphore


def mark_size_split(record_url: str) -> None:
    with webui_status_lock:
        size_split_urls.add(record_url)


def consume_size_split(record_url: str) -> bool:
    with webui_status_lock:
        if record_url not in size_split_urls:
            return False
        size_split_urls.remove(record_url)
        return True


def should_split_by_size(file_path: str) -> bool:
    limit_bytes = int(globals().get("split_file_size_bytes", 0) or 0)
    if not globals().get("split_by_size", False) or limit_bytes <= 0 or "%" in file_path:
        return False
    try:
        return os.path.isfile(file_path) and os.path.getsize(file_path) >= limit_bytes
    except OSError:
        return False


def stop_record_process(process: subprocess.Popen) -> None:
    try:
        if os.name == 'nt':
            if process.stdin:
                process.stdin.write(b'q')
                process.stdin.close()
        else:
            process.send_signal(signal.SIGINT)
    except Exception:
        process.terminate()


def size_split_file_path(save_path: str, part_index: int) -> str:
    if part_index <= 0:
        return save_path
    path = Path(save_path)
    return str(path.with_name(f"{path.stem}_{part_index:03d}{path.suffix}"))


def current_record_time_text() -> str:
    if globals().get("split_by_size", False):
        return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")[:-3]
    return time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())


def register_active_record_output(save_file_path: str) -> None:
    if not save_file_path:
        return
    with active_record_output_lock:
        active_record_outputs.add(os.path.abspath(save_file_path))


def unregister_active_record_output(save_file_path: str) -> None:
    if not save_file_path:
        return
    with active_record_output_lock:
        active_record_outputs.discard(os.path.abspath(save_file_path))


def _latest_segment_for_pattern(pattern_path: str) -> str:
    if "%03d" not in pattern_path:
        return ""
    directory = os.path.dirname(pattern_path)
    filename = os.path.basename(pattern_path)
    prefix, suffix = filename.split("%03d", maxsplit=1)
    if not os.path.isdir(directory):
        return ""
    matched_paths = [
        os.path.join(directory, filename)
        for filename in os.listdir(directory)
        if filename.startswith(prefix) and filename.endswith(suffix)
    ]
    if not matched_paths:
        return ""
    return max(matched_paths, key=lambda path: os.path.getmtime(path))


def active_record_output_paths() -> set[str]:
    with active_record_output_lock:
        outputs = list(active_record_outputs)

    active_paths: set[str] = set()
    for output_path in outputs:
        if "%03d" in output_path:
            latest_path = _latest_segment_for_pattern(output_path)
            if latest_path:
                active_paths.add(os.path.abspath(latest_path))
        else:
            active_paths.add(os.path.abspath(output_path))
    return active_paths


def auto_mp4_conversion_enabled() -> bool:
    if not bool(globals().get("scan_orphan_ts_to_mp4", False)):
        return False
    return (
        str(globals().get("video_save_type", "")).upper() == "MP4"
        or bool(globals().get("converts_to_mp4", False))
    )


def ts_conversion_roots() -> list[str]:
    configured_path = str(globals().get("video_save_path", "") or "").strip()
    root_path = configured_path or default_path
    return [os.path.abspath(root_path)]


def should_convert_ts_file(file_path: str, active_paths: set[str], now: float) -> bool:
    absolute_path = os.path.abspath(file_path)
    if absolute_path in active_paths:
        return False
    try:
        stat = os.stat(absolute_path)
    except OSError:
        return False
    if stat.st_size <= 0:
        return False
    if now - stat.st_mtime < TS_CONVERSION_STABLE_SECONDS:
        return False
    output_file_path = os.path.splitext(absolute_path)[0] + ".mp4"
    if os.path.exists(output_file_path) and os.path.getsize(output_file_path) > 0:
        if bool(globals().get("delete_origin_file", False)):
            try:
                os.remove(absolute_path)
            except OSError as exc:
                logger.error(f"删除已转换TS源文件失败: {absolute_path}, 错误: {exc}")
        return False
    return True


def scan_ts_files_for_mp4_conversion(root_path: str) -> None:
    if not root_path or not os.path.isdir(root_path):
        return
    now = time.time()
    active_paths = active_record_output_paths()
    for current_dir, _dirs, filenames in os.walk(root_path):
        for filename in filenames:
            if not filename.lower().endswith(".ts"):
                continue
            file_path = os.path.join(current_dir, filename)
            if not should_convert_ts_file(file_path, active_paths, now):
                continue
            logger.info(f"检测到遗留TS文件，自动转为MP4: {file_path}")
            converts_mp4(file_path, bool(globals().get("delete_origin_file", False)))


def ts_conversion_scanner_loop() -> None:
    while True:
        try:
            if auto_mp4_conversion_enabled():
                for root_path in ts_conversion_roots():
                    scan_ts_files_for_mp4_conversion(root_path)
        except Exception as exc:
            logger.error(f"后台TS转MP4扫描失败: {exc}")
        time.sleep(TS_CONVERSION_SCAN_SECONDS)


def start_ts_conversion_scanner() -> None:
    global ts_conversion_scanner_started
    with ts_conversion_scanner_lock:
        if ts_conversion_scanner_started:
            return
        thread = threading.Thread(target=ts_conversion_scanner_loop, name="ts-mp4-scanner", daemon=True)
        thread.start()
        ts_conversion_scanner_started = True


def default_record_history() -> dict:
    return {"version": 1, "daily": {}, "anchors": {}}


def load_record_history() -> dict:
    with record_history_lock:
        path = Path(record_history_file)
        if not path.exists():
            return default_record_history()
        try:
            with path.open("r", encoding="utf-8") as file:
                history = json.load(file)
        except (OSError, json.JSONDecodeError):
            return default_record_history()
        if not isinstance(history, dict):
            return default_record_history()
        history.setdefault("version", 1)
        if not isinstance(history.get("daily"), dict):
            history["daily"] = {}
        if not isinstance(history.get("anchors"), dict):
            history["anchors"] = {}
        return history


def save_record_history(history: dict) -> None:
    with record_history_lock:
        path = Path(record_history_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(history, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)


def parse_history_datetime(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        return value
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(str(value))
    except ValueError:
        return None


def history_anchor_display_name(record_name: str, anchor_name: str = "", record_url: str = "") -> str:
    display_name = (anchor_name or "").strip()
    if not display_name and record_name:
        display_name = record_name.split(" ", maxsplit=1)[-1].strip()
    return display_name or record_url or "未命名"


def history_anchor_key(record_url: str, anchor_name: str, record_name: str) -> str:
    return (record_url or anchor_name or record_name or "unknown").strip()


def normalize_history_count(value: Any) -> int:
    try:
        return max(0, int(float(value or 0)))
    except (TypeError, ValueError):
        return 0


def record_history_event(
        record_name: str,
        record_url: str,
        anchor_name: str,
        started_at: datetime.datetime,
        ended_at: datetime.datetime | None = None,
        avatar_url: str = "",
) -> None:
    ended_at = ended_at or datetime.datetime.now()
    duration_seconds = max(0, int((ended_at - started_at).total_seconds()))
    if duration_seconds <= 0:
        return

    day_key = ended_at.date().isoformat()
    display_name = history_anchor_display_name(record_name, anchor_name, record_url)
    anchor_key = history_anchor_key(record_url, display_name, record_name)
    avatar_url = normalize_avatar_url(avatar_url) or cached_anchor_avatar(record_url, display_name, anchor_name, record_name)
    if avatar_url:
        cache_anchor_avatar(record_url, display_name, avatar_url)

    with record_history_lock:
        history = load_record_history()
        daily = history.setdefault("daily", {})
        day_bucket = daily.get(day_key)
        if not isinstance(day_bucket, dict):
            day_bucket = {"recordings": 0, "duration_seconds": 0, "anchors": {}}
            daily[day_key] = day_bucket
        day_bucket["recordings"] = normalize_history_count(day_bucket.get("recordings")) + 1
        day_bucket["duration_seconds"] = normalize_history_count(day_bucket.get("duration_seconds")) + duration_seconds
        if not isinstance(day_bucket.get("anchors"), dict):
            day_bucket["anchors"] = {}
        day_anchors = day_bucket["anchors"]
        day_anchor = day_anchors.get(anchor_key)
        if not isinstance(day_anchor, dict):
            day_anchor = {
                "name": display_name,
                "url": record_url,
                "recordings": 0,
                "duration_seconds": 0,
            }
            day_anchors[anchor_key] = day_anchor
        day_anchor["name"] = display_name
        day_anchor["url"] = record_url
        if avatar_url:
            day_anchor["avatar_url"] = avatar_url
        day_anchor["recordings"] = normalize_history_count(day_anchor.get("recordings")) + 1
        day_anchor["duration_seconds"] = normalize_history_count(
            day_anchor.get("duration_seconds")
        ) + duration_seconds

        anchors = history.setdefault("anchors", {})
        anchor = anchors.get(anchor_key)
        if not isinstance(anchor, dict):
            anchor = {
                "name": display_name,
                "url": record_url,
                "recordings": 0,
                "duration_seconds": 0,
            }
            anchors[anchor_key] = anchor
        anchor["name"] = display_name
        anchor["url"] = record_url
        if avatar_url:
            anchor["avatar_url"] = avatar_url
        anchor["recordings"] = normalize_history_count(anchor.get("recordings")) + 1
        anchor["duration_seconds"] = normalize_history_count(anchor.get("duration_seconds")) + duration_seconds
        anchor["last_started_at"] = started_at.isoformat(timespec="seconds")
        anchor["last_recorded_at"] = ended_at.isoformat(timespec="seconds")

        cutoff_day = (ended_at.date() - datetime.timedelta(days=400)).isoformat()
        for saved_day in list(daily.keys()):
            if saved_day < cutoff_day:
                daily.pop(saved_day, None)

        save_record_history(history)


def record_history_from_active(record_name: str, record_url: str) -> None:
    with webui_status_lock:
        start_info = recording_time_list.get(record_name)
        room_status = dict(webui_room_status.get(record_url, {}))
    if not start_info:
        return
    started_at = parse_history_datetime(start_info[0])
    if not started_at:
        return
    record_history_event(
        record_name=record_name,
        record_url=record_url,
        anchor_name=room_status.get("anchor_name", ""),
        started_at=started_at,
        avatar_url=room_status.get("avatar_url", ""),
    )


def add_anchor_total(
        totals: dict,
        anchor_key: str,
        name: str,
        record_url: str,
        recordings: int,
        duration_seconds: int,
        avatar_url: str = "",
) -> None:
    if not anchor_key:
        return
    current = totals.setdefault(anchor_key, {
        "name": name or record_url or "未命名",
        "url": record_url,
        "avatar_url": "",
        "recordings": 0,
        "duration_seconds": 0,
    })
    if name:
        current["name"] = name
    if record_url:
        current["url"] = record_url
    avatar_url = normalize_avatar_url(avatar_url) or cached_anchor_avatar(record_url, name)
    if avatar_url:
        current["avatar_url"] = avatar_url
    current["recordings"] += normalize_history_count(recordings)
    current["duration_seconds"] += normalize_history_count(duration_seconds)


def get_record_history_summary(active_rows: list[dict], allowed_urls: set[str] | None = None) -> dict:
    now = datetime.datetime.now()
    today_key = now.date().isoformat()
    history = load_record_history()
    daily = history.get("daily", {})
    ranges: dict[str, dict] = {}
    range_days = (7, 30, 90, 365)
    allowed_url_set = {url for url in (allowed_urls or set()) if url} if allowed_urls is not None else None

    active_today_recordings = 0
    active_today_duration = 0
    active_anchor_totals: dict[str, dict] = {}
    for row in active_rows:
        row_url = str(row.get("url") or "")
        if allowed_url_set is not None and row_url not in allowed_url_set:
            continue
        elapsed_seconds = normalize_history_count(row.get("elapsed_seconds"))
        if elapsed_seconds <= 0:
            started_at = parse_history_datetime(row.get("started_at"))
            if started_at:
                elapsed_seconds = max(0, int((now - started_at).total_seconds()))
        if elapsed_seconds <= 0:
            continue
        active_today_recordings += 1
        active_today_duration += elapsed_seconds
        display_name = history_anchor_display_name(
            str(row.get("name") or ""),
            str(row.get("anchor_name") or ""),
            row_url,
        )
        anchor_key = history_anchor_key(row_url, display_name, str(row.get("name") or ""))
        add_anchor_total(
            active_anchor_totals,
            anchor_key,
            display_name,
            row_url,
            1,
            elapsed_seconds,
            str(row.get("avatar_url") or ""),
        )

    for days in range_days:
        start_date = now.date() - datetime.timedelta(days=days - 1)
        day_rows = []
        range_recordings = 0
        range_duration = 0
        anchor_totals: dict[str, dict] = {}
        for index in range(days):
            day_date = start_date + datetime.timedelta(days=index)
            day_key = day_date.isoformat()
            bucket = daily.get(day_key, {}) if isinstance(daily.get(day_key), dict) else {}
            recordings = 0
            duration_seconds = 0
            bucket_anchors = bucket.get("anchors", {}) if isinstance(bucket.get("anchors"), dict) else {}
            if allowed_url_set is None:
                recordings = normalize_history_count(bucket.get("recordings"))
                duration_seconds = normalize_history_count(bucket.get("duration_seconds"))
            else:
                for anchor in bucket_anchors.values():
                    if not isinstance(anchor, dict) or str(anchor.get("url") or "") not in allowed_url_set:
                        continue
                    recordings += normalize_history_count(anchor.get("recordings"))
                    duration_seconds += normalize_history_count(anchor.get("duration_seconds"))
            if day_key == today_key:
                recordings += active_today_recordings
                duration_seconds += active_today_duration

            range_recordings += recordings
            range_duration += duration_seconds
            day_rows.append({
                "date": day_key,
                "label": day_date.strftime("%m-%d"),
                "recordings": recordings,
                "duration_seconds": duration_seconds,
            })

            for anchor_key, anchor in bucket_anchors.items():
                if not isinstance(anchor, dict):
                    continue
                if allowed_url_set is not None and str(anchor.get("url") or "") not in allowed_url_set:
                    continue
                add_anchor_total(
                    anchor_totals,
                    str(anchor_key),
                    str(anchor.get("name") or ""),
                    str(anchor.get("url") or ""),
                    normalize_history_count(anchor.get("recordings")),
                    normalize_history_count(anchor.get("duration_seconds")),
                    str(anchor.get("avatar_url") or ""),
                )
            if day_key == today_key:
                for anchor_key, anchor in active_anchor_totals.items():
                    add_anchor_total(
                        anchor_totals,
                        anchor_key,
                        anchor.get("name", ""),
                        anchor.get("url", ""),
                        anchor.get("recordings", 0),
                        anchor.get("duration_seconds", 0),
                        anchor.get("avatar_url", ""),
                    )

        anchor_top = sorted(
            anchor_totals.values(),
            key=lambda item: (item.get("duration_seconds", 0), item.get("recordings", 0), item.get("name", "")),
            reverse=True,
        )[:20]
        ranges[str(days)] = {
            "label": "全年" if days == 365 else f"{days}天",
            "days": day_rows,
            "recordings": range_recordings,
            "duration_seconds": range_duration,
            "anchor_top": anchor_top,
        }

    return {
        "updated_at": now.isoformat(timespec="seconds"),
        "ranges": ranges,
    }


def get_webui_status_snapshot() -> dict:
    now = datetime.datetime.now()
    with webui_status_lock:
        rooms_status = [dict(item) for item in webui_room_status.values()]
        recording_names = list(recording)
        recording_time_snapshot = dict(recording_time_list)
        running_urls_snapshot = list(running_list)
        disabled_urls_snapshot = list(url_comments)
        monitoring_snapshot = monitoring

    for room_status in rooms_status:
        if not room_status.get("avatar_url"):
            room_status["avatar_url"] = cached_anchor_avatar(
                room_status.get("url", ""),
                room_status.get("anchor_name", ""),
                room_status.get("configured_name", ""),
                room_status.get("record_name", ""),
            )

    recording_rows = []
    disabled_url_set = set(disabled_urls_snapshot)
    status_by_record_name = {
        item.get("record_name"): item
        for item in rooms_status
        if item.get("record_name")
    }
    for recording_live in recording_names:
        start_info = recording_time_snapshot.get(recording_live)
        if not start_info:
            continue
        started_at, quality = start_info
        room_status = status_by_record_name.get(recording_live, {})
        recording_rows.append({
            "name": recording_live,
            "url": room_status.get("url", ""),
            "group": room_status.get("group", "") or room_status.get("configured_group", ""),
            "platform": room_status.get("platform", ""),
            "anchor_name": room_status.get("anchor_name", ""),
            "avatar_url": room_status.get("avatar_url", ""),
            "quality": quality,
            "started_at": started_at.isoformat(timespec="seconds"),
            "elapsed_seconds": int((now - started_at).total_seconds()),
        })

    return {
        "version": version,
        "monitoring": monitoring_snapshot,
        "running_count": len(running_urls_snapshot),
        "recording_count": len(recording_rows),
        "recording": recording_rows,
        "rooms": rooms_status,
        "running_urls": running_urls_snapshot,
        "disabled_urls": disabled_urls_snapshot,
        "instant_error_count": error_count,
        "room_error_count": sum(
            1 for item in rooms_status
            if item.get("status") == "error" and item.get("url") not in disabled_url_set
        ),
        "error_count": error_count,
        "max_request": globals().get("max_request", pre_max_request),
        "delay_default": globals().get("delay_default", 0),
        "video_record_quality": globals().get("video_record_quality", ""),
        "video_save_type": globals().get("video_save_type", ""),
        "use_proxy": globals().get("use_proxy", False),
        "uptime_seconds": int((now - program_start_time).total_seconds()),
        "system_metrics": get_system_metrics(),
    }


def request_webui_stop_urls(urls: list[str]) -> None:
    for url in urls:
        if not url:
            continue
        normalized_url = url.strip()
        if normalized_url and '://' not in normalized_url:
            normalized_url = 'https://' + normalized_url
        if normalized_url:
            with webui_status_lock:
                if normalized_url not in url_comments:
                    url_comments.append(normalized_url)
            update_webui_room_status(normalized_url, status="stopped", message="已请求停止", next_check_at="")


def update_next_check_time(record_url: str, seconds: int | float) -> None:
    seconds = max(0, int(seconds or 0))
    if seconds <= 0:
        update_webui_room_status(record_url, next_check_at="")
        return
    next_check_at = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
    update_webui_room_status(record_url, next_check_at=next_check_at.isoformat(timespec="seconds"))


def schedule_room_check(record_url: str, seconds: int | float) -> None:
    seconds = max(0, int(seconds or 0))
    with room_dispatch_lock:
        room_next_check_monotonic[record_url] = time.monotonic() + seconds
    update_next_check_time(record_url, seconds)
    room_dispatch_event.set()


def persist_room_worker_state(
        record_url: str,
        record_finished: bool,
        run_once: bool,
        start_pushed: bool,
        new_record_url: str,
        count_time: float,
) -> None:
    with room_dispatch_lock:
        room_worker_states[record_url] = {
            "record_finished": record_finished,
            "run_once": run_once,
            "start_pushed": start_pushed,
            "new_record_url": new_record_url,
            "count_time": count_time,
        }


def run_room_worker(url_data: tuple, count_variable: int) -> None:
    record_url = url_data[1]
    try:
        start_record(url_data, count_variable)
    finally:
        stopped = is_stop_requested(record_url)
        with room_dispatch_lock:
            room_worker_threads.pop(record_url, None)
            if (
                    record_url in room_monitor_configs
                    and record_url not in room_next_check_monotonic
                    and not stopped
            ):
                room_next_check_monotonic[record_url] = time.monotonic() + 2
        room_dispatch_event.set()


def room_dispatcher_loop() -> None:
    while True:
        now = time.monotonic()
        with webui_status_lock:
            recording_urls = {
                record_url for record_url, status in webui_room_status.items()
                if status.get("status") == "recording"
            }
        with room_dispatch_lock:
            active_check_count = sum(
                1 for record_url in room_worker_threads
                if record_url not in recording_urls
            )
            available_slots = max(0, int(globals().get("max_request", 1)) - active_check_count)
            due_urls = sorted(
                (
                    (due_at, record_url)
                    for record_url, due_at in room_next_check_monotonic.items()
                    if due_at <= now
                    and record_url in room_monitor_configs
                    and record_url not in room_worker_threads
                ),
                key=lambda item: item[0],
            )[:available_slots]

            for _due_at, record_url in due_urls:
                url_data = room_monitor_configs[record_url]
                room_next_check_monotonic.pop(record_url, None)
                try:
                    count_variable = running_list.index(record_url) + 1
                except ValueError:
                    count_variable = -1
                worker = threading.Thread(
                    target=run_room_worker,
                    args=(url_data, count_variable),
                    name=f"room-check-{count_variable}",
                    daemon=True,
                )
                room_worker_threads[record_url] = worker
                worker.start()

            future_checks = [
                due_at for record_url, due_at in room_next_check_monotonic.items()
                if record_url in room_monitor_configs and record_url not in room_worker_threads
            ]

        timeout = 1.0
        if future_checks:
            timeout = max(0.1, min(1.0, min(future_checks) - time.monotonic()))
        room_dispatch_event.wait(timeout)
        room_dispatch_event.clear()


def ensure_room_dispatcher_started() -> None:
    global room_dispatcher_started
    with room_dispatcher_lock:
        if room_dispatcher_started:
            return
        threading.Thread(target=room_dispatcher_loop, name="room-dispatcher", daemon=True).start()
        room_dispatcher_started = True


def signal_handler(_signal, _frame):
    sys.exit(0)


signal.signal(signal.SIGTERM, signal_handler)


def display_info() -> None:
    global start_display_time
    time.sleep(status_refresh_seconds())
    while True:
        try:
            time.sleep(status_refresh_seconds())
            if not globals().get("show_status_panel", True):
                continue
            if Path(sys.executable).name != 'pythonw.exe' and globals().get("clear_status_panel", False):
                os.system(clear_command)
            with webui_status_lock:
                recording_names = list(set(recording))
                recording_time_snapshot = dict(recording_time_list)
                monitoring_snapshot = monitoring

            print(f"\r共监测{monitoring_snapshot}个直播中", end=" | ")
            print(f"同一时间访问网络的线程数: {max_request}", end=" | ")
            print(f"是否开启代理录制: {'是' if use_proxy else '否'}", end=" | ")
            if split_video_by_time:
                if split_by_size:
                    print(f"录制分段开启: {split_file_size_mb:g}MB", end=" | ")
                else:
                    print(f"录制分段开启: {split_time}秒", end=" | ")
            else:
                print("录制分段开启: 否", end=" | ")
            if create_subtitle_file:
                print(f"是否生成字幕文件({subtitle_content_mode()}): 是", end=" | ")
            if globals().get("burn_subtitle_to_video", False):
                print("是否烧录字幕: 是", end=" | ")
            print(f"录制视频质量为: {video_record_quality}", end=" | ")
            print(f"录制视频格式为: {video_save_type}", end=" | ")
            print(f"目前瞬时错误数为: {error_count}", end=" | ")
            now = time.strftime("%H:%M:%S", time.localtime())
            print(f"当前时间: {now}")

            if len(recording_names) == 0:
                time.sleep(5)
                if monitoring_snapshot == 0:
                    print("\r没有正在监测和录制的直播")
                else:
                    print(f"\r没有正在录制的直播 循环监测间隔时间：{delay_default}秒")
            else:
                now_time = datetime.datetime.now()
                print("x" * 60)
                print(f"正在录制{len(recording_names)}个直播: ")
                for recording_live in recording_names:
                    start_info = recording_time_snapshot.get(recording_live)
                    if not start_info:
                        continue
                    rt, qa = start_info
                    have_record_time = now_time - rt
                    print(f"{recording_live}[{qa}] 正在录制中 {str(have_record_time).split('.')[0]}")

                # print('\n本软件已运行：'+str(now_time - start_display_time).split('.')[0])
                print("x" * 60)
                start_display_time = now_time
        except Exception as e:
            logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")


def update_file(file_path: str, old_str: str, new_str: str, start_str: str = None) -> str | None:
    if old_str == new_str and start_str is None:
        return old_str
    with file_update_lock:
        file_data = []
        with open(file_path, "r", encoding=text_encoding) as f:
            try:
                for text_line in f:
                    if old_str in text_line:
                        text_line = text_line.replace(old_str, new_str)
                        if start_str:
                            text_line = f'{start_str}{text_line}'
                    if text_line not in file_data:
                        file_data.append(text_line)
            except RuntimeError as e:
                logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                if ini_URL_content:
                    with open(file_path, "w", encoding=text_encoding) as f2:
                        f2.write(ini_URL_content)
                    return old_str
        if file_data:
            with open(file_path, "w", encoding=text_encoding) as f:
                f.write(''.join(file_data))
        return new_str


def delete_line(file_path: str, del_line: str, delete_all: bool = False) -> None:
    with file_update_lock:
        with open(file_path, 'r+', encoding=text_encoding) as f:
            lines = f.readlines()
            f.seek(0)
            f.truncate()
            skip_line = False
            for txt_line in lines:
                if del_line in txt_line:
                    if delete_all or not skip_line:
                        skip_line = True
                        continue
                else:
                    skip_line = False
                f.write(txt_line)


def get_startup_info(system_type: str):
    if system_type == 'nt':
        startup_info = subprocess.STARTUPINFO()
        startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        startup_info = None
    return startup_info


def segment_video(converts_file_path: str, segment_save_file_path: str, segment_format: str, segment_time: str,
                  is_original_delete: bool = True) -> None:
    try:
        if os.path.exists(converts_file_path) and os.path.getsize(converts_file_path) > 0:
            ffmpeg_command = [
                "ffmpeg",
                "-nostats",
                "-loglevel", "error",
                "-i", converts_file_path,
                *ffmpeg_thread_args(),
                "-c:v", "copy",
                "-c:a", "copy",
                "-map", "0",
                "-f", "segment",
                "-segment_time", segment_time,
                "-segment_format", segment_format,
                "-reset_timestamps", "1",
                "-movflags", "+frag_keyframe+empty_moov",
                segment_save_file_path,
            ]
            _output = subprocess.check_output(
                ffmpeg_command, stderr=subprocess.STDOUT, startupinfo=get_startup_info(os_type)
            )
            if is_original_delete:
                time.sleep(1)
                if os.path.exists(converts_file_path):
                    os.remove(converts_file_path)
    except subprocess.CalledProcessError as e:
        logger.error(f'Error occurred during conversion: {e}')
    except Exception as e:
        logger.error(f'An unknown error occurred: {e}')


def start_mp4_conversion(
        converts_file_path: str,
        is_original_delete: bool = True,
        burn_subtitle: bool = False,
) -> None:
    output_file_path = conversion_output_path(converts_file_path)
    source_file_path = converts_file_path
    claimed_source_path = ""
    if burn_subtitle or bool(globals().get("burn_subtitle_to_video", False)):
        try:
            source_file_path = claim_conversion_source(converts_file_path)
            claimed_source_path = converts_file_path
        except OSError as exc:
            logger.error(f"准备烧录字幕时占用源文件失败，跳过转码: {converts_file_path}, 错误: {exc}")
            return
    threading.Thread(
        target=converts_mp4,
        args=(source_file_path, is_original_delete, burn_subtitle, output_file_path, claimed_source_path),
    ).start()


def subprocess_output_text(exc: subprocess.CalledProcessError) -> str:
    output = exc.output or b""
    if isinstance(output, bytes):
        output_text = output.decode("utf-8", errors="ignore")
    else:
        output_text = str(output)
    return output_text.strip()[-2000:]


def conversion_output_path(source_file_path: str) -> str:
    return source_file_path.rsplit('.', maxsplit=1)[0] + ".mp4"


def conversion_processing_dir(reference_file_path: str) -> str:
    processing_dir = os.path.join(os.path.dirname(reference_file_path), CONVERSION_PROCESSING_DIR_NAME)
    os.makedirs(processing_dir, exist_ok=True)
    return processing_dir


def conversion_processing_path(reference_file_path: str, suffix: str) -> str:
    return os.path.join(
        conversion_processing_dir(reference_file_path),
        f"{Path(reference_file_path).stem}.{os.getpid()}-{threading.get_ident()}-{uuid.uuid4().hex}.{suffix}",
    )


def cleanup_conversion_processing_dir(reference_file_path: str) -> None:
    processing_dir = os.path.join(os.path.dirname(reference_file_path), CONVERSION_PROCESSING_DIR_NAME)
    try:
        if os.path.isdir(processing_dir) and not os.listdir(processing_dir):
            os.rmdir(processing_dir)
    except OSError:
        pass


def claim_conversion_source(source_file_path: str) -> str:
    work_source_path = conversion_processing_path(source_file_path, "source")
    os.replace(source_file_path, work_source_path)
    return work_source_path


def restore_conversion_source(work_source_path: str, original_source_path: str) -> None:
    if not work_source_path or not original_source_path or not os.path.exists(work_source_path):
        return
    if os.path.exists(original_source_path):
        return
    try:
        os.replace(work_source_path, original_source_path)
    except OSError as exc:
        logger.error(f"恢复转码源文件失败: {work_source_path} -> {original_source_path}, 错误: {exc}")


def wait_for_file_stable(file_path: str, timeout_seconds: int, stable_seconds: int) -> bool:
    deadline = time.time() + max(0, timeout_seconds)
    last_state: tuple[int, int] | None = None
    stable_since = 0.0
    while time.time() <= deadline:
        try:
            stat = os.stat(file_path)
            if stat.st_size > 0:
                state = (stat.st_size, stat.st_mtime_ns)
                now = time.time()
                if state == last_state:
                    if stable_since and now - stable_since >= stable_seconds:
                        return True
                else:
                    last_state = state
                    stable_since = now
        except OSError:
            last_state = None
            stable_since = 0.0
        time.sleep(0.5)
    try:
        return os.path.exists(file_path) and os.path.getsize(file_path) > 0
    except OSError:
        return False


def ffmpeg_filter_escape(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


def subtitle_file_for_video(video_file_path: str) -> tuple[str, float]:
    subtitle_file_path = f"{normalize_subtitle_base_path(video_file_path)}.ass"
    if os.path.exists(subtitle_file_path):
        return subtitle_file_path, 0

    path = Path(video_file_path)
    match = re.search(r"_(\d{3,})$", path.stem)
    if not match or not globals().get("split_by_time", False):
        return subtitle_file_path, 0

    source_subtitle_path = str(path.with_name(re.sub(r"_\d{3,}$", "", path.stem) + ".ass"))
    try:
        segment_index = int(match.group(1))
        segment_seconds = float(str(globals().get("split_time", 0) or 0))
    except (TypeError, ValueError):
        return source_subtitle_path, 0
    return source_subtitle_path, max(0, segment_index * segment_seconds)


def subtitle_burn_filter(subtitle_file_path: str) -> str:
    return f"subtitles='{ffmpeg_filter_escape(subtitle_file_path)}',format=yuv420p"


def ass_time_seconds(value: str) -> float:
    match = re.match(r"(\d+):(\d{2}):(\d{2})[.](\d{2})", str(value or "").strip())
    if not match:
        return 0
    hours, minutes, seconds, centiseconds = [int(part) for part in match.groups()]
    return hours * 3600 + minutes * 60 + seconds + centiseconds / 100


def shifted_ass_subtitle_file(source_path: str, temp_path: str, offset_seconds: float) -> str:
    segment_seconds = 0.0
    try:
        segment_seconds = float(str(globals().get("split_time", 0) or 0))
    except (TypeError, ValueError):
        pass

    with open(source_path, "r", encoding=text_encoding) as source, open(temp_path, "w", encoding=text_encoding) as target:
        for line in source:
            if not line.startswith("Dialogue:"):
                target.write(line)
                continue
            fields = line.rstrip("\n").split(",", 9)
            if len(fields) < 10:
                target.write(line)
                continue
            start_seconds = ass_time_seconds(fields[1]) - offset_seconds
            end_seconds = ass_time_seconds(fields[2]) - offset_seconds
            if end_seconds <= 0 or (segment_seconds > 0 and start_seconds >= segment_seconds):
                continue
            shifted_start = max(0, start_seconds)
            if segment_seconds > 0:
                end_seconds = min(end_seconds, segment_seconds)
            shifted_end = max(shifted_start + 0.01, end_seconds)
            fields[1] = ass_time_text(shifted_start)
            fields[2] = ass_time_text(shifted_end)
            target.write(",".join(fields) + "\n")
    return temp_path


def burn_ready_ass_subtitle_file(source_path: str, temp_path: str, offset_seconds: float = 0) -> str:
    segment_seconds = 0.0
    try:
        segment_seconds = float(str(globals().get("split_time", 0) or 0))
    except (TypeError, ValueError):
        pass

    with open(source_path, "r", encoding=text_encoding) as source, open(temp_path, "w", encoding=text_encoding) as target:
        for line in source:
            if line.startswith("Style: Danmu,"):
                target.write(
                    f"Style: Danmu,{DANMU_FONT_NAME},{DANMU_FONT_SIZE},&H00FFFFFF,&H000000FF,"
                    f"{DANMU_BOX_COLOR},{DANMU_BOX_COLOR},"
                    f"0,0,0,0,100,100,0,0,3,{DANMU_BOX_PADDING},0,1,{DANMU_REGION_LEFT},"
                    f"{DANMU_REGION_RIGHT_MARGIN},{DANMU_REGION_VERTICAL_MARGIN},1\n"
                )
                continue
            if not line.startswith("Dialogue:"):
                target.write(line)
                continue
            fields = line.rstrip("\n").split(",", 9)
            if len(fields) < 10:
                target.write(line)
                continue
            if offset_seconds > 0:
                start_seconds = ass_time_seconds(fields[1]) - offset_seconds
                end_seconds = ass_time_seconds(fields[2]) - offset_seconds
                if end_seconds <= 0 or (segment_seconds > 0 and start_seconds >= segment_seconds):
                    continue
                shifted_start = max(0, start_seconds)
                if segment_seconds > 0:
                    end_seconds = min(end_seconds, segment_seconds)
                shifted_end = max(shifted_start + 0.01, end_seconds)
                fields[1] = ass_time_text(shifted_start)
                fields[2] = ass_time_text(shifted_end)
            text = fields[9]
            text = text.replace(r"\q0", r"\q2").replace(r"\q1", r"\q2").replace(r"\q3", r"\q2")
            text = re.sub(r"\\fad\([^)]*\)", "", text)
            text = re.sub(r"\\blur[0-9.]+", "", text)
            text = re.sub(r"\\be[0-9.]+", "", text)
            text = re.sub(r"\\shad[0-9.]+", "", text)
            if text.startswith("{"):
                text = "{\\q2\\blur0\\be0\\shad0" + text[1:]
            else:
                text = "{\\q2\\blur0\\be0\\shad0}" + text
            fields[9] = text
            target.write(",".join(fields) + "\n")
    return temp_path


def get_segment_source_paths(save_file_path: str) -> list[str]:
    file_paths = utils.get_file_paths(os.path.dirname(save_file_path))
    prefix = os.path.basename(save_file_path).rsplit('_', maxsplit=1)[0]
    suffix = Path(save_file_path).suffix.lower()
    return sorted(
        path for path in file_paths
        if os.path.basename(path).startswith(prefix) and Path(path).suffix.lower() == suffix
    )


def start_segment_mp4_conversions(
        save_file_path: str,
        is_original_delete: bool = True,
        burn_subtitle: bool = False,
) -> None:
    segment_paths = get_segment_source_paths(save_file_path)
    if not segment_paths:
        return

    def convert_segments() -> None:
        for path in segment_paths:
            converts_mp4(path, is_original_delete, burn_subtitle)

    threading.Thread(target=convert_segments, name=f"mp4-segments-{Path(save_file_path).stem}").start()


def converts_mp4(
        converts_file_path: str,
        is_original_delete: bool = True,
        burn_subtitle: bool = False,
        output_file_path: str = "",
        claimed_source_path: str = "",
) -> None:
    original_source_path = claimed_source_path or converts_file_path
    normalized_file_path = os.path.abspath(original_source_path)
    with mp4_convert_lock:
        if normalized_file_path in mp4_converting_files:
            logger.debug(f"跳过重复MP4转码任务: {original_source_path}")
            if claimed_source_path:
                restore_conversion_source(converts_file_path, claimed_source_path)
            return
        mp4_converting_files.add(normalized_file_path)

    temp_output_file_path = ""
    temp_subtitle_file_path = ""
    conversion_succeeded = False
    conversion_slot = current_mp4_convert_semaphore()
    if not conversion_slot.acquire(blocking=False):
        logger.info(f"MP4转码排队中，当前并发上限: {mp4_convert_semaphore_limit}")
        conversion_slot.acquire()
    try:
        if os.path.exists(converts_file_path) and os.path.getsize(converts_file_path) > 0:
            output_file_path = output_file_path or conversion_output_path(converts_file_path)
            temp_output_file_path = conversion_processing_path(output_file_path, "tmp")
            burn_requested = burn_subtitle or bool(globals().get("burn_subtitle_to_video", False))
            subtitle_file_path, subtitle_offset_seconds = subtitle_file_for_video(original_source_path)
            should_burn_subtitle = burn_requested and wait_for_file_stable(
                subtitle_file_path,
                SUBTITLE_BURN_WAIT_TIMEOUT_SECONDS,
                SUBTITLE_BURN_STABLE_SECONDS,
            )
            if burn_requested and not should_burn_subtitle:
                logger.warning(f"已开启字幕烧录，但未找到有效ASS字幕文件，跳过烧录: {subtitle_file_path}")

            if should_burn_subtitle:
                temp_subtitle_file_path = conversion_processing_path(output_file_path, "burn.ass")
                burn_subtitle_file_path = burn_ready_ass_subtitle_file(
                    subtitle_file_path, temp_subtitle_file_path, subtitle_offset_seconds
                )
                color_obj.print_colored("正在转码为MP4格式并烧录字幕\n", color_obj.YELLOW)
                ffmpeg_command = [
                    "ffmpeg", "-y", "-nostats", "-loglevel", "error", "-i", converts_file_path,
                    *ffmpeg_thread_args(),
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-vf", subtitle_burn_filter(burn_subtitle_file_path),
                    "-c:a", "copy",
                    *mp4_movflags_args(),
                    "-f", "mp4", temp_output_file_path,
                ]
            elif converts_to_h264:
                color_obj.print_colored("正在转码为MP4格式并重新编码为h264\n", color_obj.YELLOW)
                ffmpeg_command = [
                    "ffmpeg", "-y", "-nostats", "-loglevel", "error", "-i", converts_file_path,
                    *ffmpeg_thread_args(),
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "23",
                    "-vf", "format=yuv420p",
                    "-c:a", "copy",
                    *mp4_movflags_args(),
                    "-f", "mp4", temp_output_file_path,
                ]
            else:
                color_obj.print_colored("正在转码为MP4格式\n", color_obj.YELLOW)
                ffmpeg_command = [
                    "ffmpeg", "-y", "-nostats", "-loglevel", "error", "-i", converts_file_path,
                    *ffmpeg_thread_args(),
                    "-c:v", "copy",
                    "-c:a", "copy",
                    *mp4_movflags_args(),
                    "-f", "mp4", temp_output_file_path,
                ]
            _output = subprocess.check_output(
                ffmpeg_command, stderr=subprocess.STDOUT, startupinfo=get_startup_info(os_type)
            )
            if os.path.exists(temp_output_file_path) and os.path.getsize(temp_output_file_path) > 0:
                os.replace(temp_output_file_path, output_file_path)
                conversion_succeeded = True
                logger.info(f"MP4转码完成: {output_file_path}")
            else:
                logger.error(f"MP4转码失败，未生成有效文件: {output_file_path}")
            if conversion_succeeded and is_original_delete:
                time.sleep(1)
                if (
                    os.path.exists(converts_file_path)
                    and (
                        claimed_source_path
                        or os.path.abspath(converts_file_path) != os.path.abspath(output_file_path)
                    )
                ):
                    os.remove(converts_file_path)
            elif conversion_succeeded and claimed_source_path:
                if os.path.abspath(claimed_source_path) != os.path.abspath(output_file_path):
                    restore_conversion_source(converts_file_path, claimed_source_path)
                elif os.path.exists(converts_file_path):
                    os.remove(converts_file_path)
    except subprocess.CalledProcessError as e:
        logger.error(f'Error occurred during conversion: {e}; ffmpeg output: {subprocess_output_text(e)}')
    except Exception as e:
        logger.error(f'An unknown error occurred: {e}')
    finally:
        conversion_slot.release()
        if claimed_source_path and not conversion_succeeded:
            restore_conversion_source(converts_file_path, claimed_source_path)
        if temp_output_file_path and os.path.exists(temp_output_file_path):
            try:
                os.remove(temp_output_file_path)
            except OSError:
                pass
        if temp_subtitle_file_path and os.path.exists(temp_subtitle_file_path):
            try:
                os.remove(temp_subtitle_file_path)
            except OSError:
                pass
        cleanup_conversion_processing_dir(output_file_path or original_source_path)
        with mp4_convert_lock:
            mp4_converting_files.discard(normalized_file_path)


def converts_m4a(converts_file_path: str, is_original_delete: bool = True) -> None:
    try:
        if os.path.exists(converts_file_path) and os.path.getsize(converts_file_path) > 0:
            _output = subprocess.check_output([
                "ffmpeg", "-nostats", "-loglevel", "error", "-i", converts_file_path,
                *ffmpeg_thread_args(),
                "-n", "-vn",
                "-c:a", "aac", "-bsf:a", "aac_adtstoasc", "-ab", "320k",
                converts_file_path.rsplit('.', maxsplit=1)[0] + ".m4a",
            ], stderr=subprocess.STDOUT, startupinfo=get_startup_info(os_type))
            if is_original_delete:
                time.sleep(1)
                if os.path.exists(converts_file_path):
                    os.remove(converts_file_path)
    except subprocess.CalledProcessError as e:
        logger.error(f'Error occurred during conversion: {e}')
    except Exception as e:
        logger.error(f'An unknown error occurred: {e}')


def generate_subtitles(record_name: str, ass_filename: str, sub_format: str = 'srt') -> None:
    index_time = 0
    today = datetime.datetime.now()
    re_datatime = today.strftime('%Y-%m-%d %H:%M:%S')

    def transform_int_to_time(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    while True:
        index_time += 1
        txt = str(index_time) + "\n" + transform_int_to_time(index_time) + ',000 --> ' + transform_int_to_time(
            index_time + 1) + ',000' + "\n" + str(re_datatime) + "\n\n"

        with open(f"{ass_filename}.{sub_format.lower()}", 'a', encoding=text_encoding) as f:
            f.write(txt)

        if record_name not in recording:
            return
        time.sleep(1)
        today = datetime.datetime.now()
        re_datatime = today.strftime('%Y-%m-%d %H:%M:%S')


def srt_time_text(seconds: float) -> str:
    seconds = max(0, seconds)
    millis = int(seconds * 1000)
    h, remainder = divmod(millis, 3600 * 1000)
    m, remainder = divmod(remainder, 60 * 1000)
    s, ms = divmod(remainder, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def ass_time_text(seconds: float) -> str:
    seconds = max(0, seconds)
    centiseconds = int(seconds * 100)
    h, remainder = divmod(centiseconds, 3600 * 100)
    m, remainder = divmod(remainder, 60 * 100)
    s, cs = divmod(remainder, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def replace_douyin_emoji_tags(value: Any) -> str:
    text = str(value or "")

    def replace_tag(match: re.Match) -> str:
        emoji_name = match.group(1).strip()
        return DOUYIN_EMOJI_TEXT_MAP.get(emoji_name, match.group(0))

    text = DOUYIN_EMOJI_TAG_PATTERN.sub(replace_tag, text)
    stripped_text = text.strip()
    if stripped_text in DOUYIN_EMOJI_TEXT_MAP:
        return text.replace(stripped_text, DOUYIN_EMOJI_TEXT_MAP[stripped_text], 1)
    return text


def clean_subtitle_text(value: Any) -> str:
    return re.sub(r"\s+", " ", replace_douyin_emoji_tags(value)).strip()


def clean_ass_text(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("{", "（").replace("}", "）")


def ass_subtitle_header() -> str:
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        f"PlayResX: {ASS_PLAY_RES_X}\n"
        f"PlayResY: {ASS_PLAY_RES_Y}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Danmu,{DANMU_FONT_NAME},{DANMU_FONT_SIZE},&H00FFFFFF,&H000000FF,{DANMU_BOX_COLOR},{DANMU_BOX_COLOR},"
        f"0,0,0,0,100,100,0,0,3,{DANMU_BOX_PADDING},0,1,{DANMU_REGION_LEFT},{DANMU_REGION_RIGHT_MARGIN},"
        f"{DANMU_REGION_VERTICAL_MARGIN},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def ensure_ass_subtitle_file(file_path: str) -> None:
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return
    except OSError:
        pass
    with open(file_path, 'w', encoding=text_encoding) as f:
        f.write(ass_subtitle_header())


def danmu_scroll_effect() -> str:
    return (
        f"Scroll up;{DANMU_REGION_TOP};{DANMU_REGION_BOTTOM};"
        f"{DANMU_SCROLL_DELAY_MS};{DANMU_REGION_FADE_HEIGHT}"
    )


def danmu_ass_prefix() -> str:
    return (
        "{"
        r"\q2\blur0\be0\shad0"
        rf"\clip(0,{DANMU_REGION_TOP},{DANMU_REGION_RIGHT},{DANMU_REGION_BOTTOM})"
        "}"
    )


def compact_danmu_text(text: str, max_chars: int = DANMU_MAX_TEXT_CHARS) -> str:
    value = clean_subtitle_text(text)
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "..."


def format_danmu_ass_text(nick_name: str, content: str) -> str:
    nick_name = compact_danmu_text(nick_name, 16)
    content = compact_danmu_text(content, DANMU_MAX_TEXT_CHARS)
    return (
        r"{\c&HFFD663&}"
        f"{clean_ass_text(nick_name)}"
        r"{\c&HFFFFFF&}: "
        f"{clean_ass_text(content)}"
    )


def douyin_live_id_from_url(record_url: str) -> str:
    match = re.search(r"live\.douyin\.com/([^/?#]+)", record_url or "")
    return match.group(1) if match else ""


def normalize_subtitle_base_path(save_file_path: str) -> str:
    base_path = save_file_path.rsplit('.', maxsplit=1)[0]
    return base_path.replace("_%03d", "").replace("%03d", "segments")


def generate_douyin_danmu_subtitles(
        record_name: str,
        record_url: str,
        room_id: str,
        live_id: str,
        subs_file_path: str,
        sub_format: str = 'srt',
) -> None:
    if not room_id:
        logger.warning(f"{record_name} 未获取到抖音 room_id，无法录制弹幕")
        return

    try:
        import websocket
        from douyin_live_chat import DouyinLiveWebFetcher
        from douyin_live_chat.protobuf.douyin import ChatMessage, PushFrame
    except Exception as e:
        logger.error(f"{record_name} 录制弹幕依赖缺失: {e}")
        return

    subtitle_file = f"{subs_file_path}.{sub_format.lower()}"
    ass_subtitle_file = f"{subs_file_path}.ass"
    start_time = time.monotonic()
    index_lock = threading.Lock()
    seen_lock = threading.Lock()
    seen_messages: dict[tuple[str, str], float] = {}
    index = 0

    def write_chat(chat_data: dict[str, Any]) -> None:
        nonlocal index
        content = clean_subtitle_text(chat_data.get("content"))
        if not content:
            return
        nick_name = clean_subtitle_text(chat_data.get("nick_name")) or "匿名用户"
        dedupe_key = (nick_name, content)
        now_monotonic = time.monotonic()
        with seen_lock:
            for old_key, old_time in list(seen_messages.items()):
                if now_monotonic - old_time > 8:
                    seen_messages.pop(old_key, None)
            if dedupe_key in seen_messages:
                return
            seen_messages[dedupe_key] = now_monotonic

        elapsed = now_monotonic - start_time
        line = f"{nick_name}: {content}"
        with index_lock:
            index += 1
            srt_text = (
                f"{index}\n"
                f"{srt_time_text(elapsed)} --> {srt_time_text(elapsed + 4)}\n"
                f"{line}\n\n"
            )
            with open(subtitle_file, 'a', encoding=text_encoding) as f:
                f.write(srt_text)

            ensure_ass_subtitle_file(ass_subtitle_file)
            ass_text = (
                f"Dialogue: 0,{ass_time_text(elapsed)},"
                f"{ass_time_text(elapsed + DANMU_SCROLL_DURATION_SECONDS)},Danmu,,0,0,0,"
                f"{danmu_scroll_effect()},{danmu_ass_prefix()}{format_danmu_ass_text(nick_name, content)}\n"
            )
            with open(ass_subtitle_file, 'a', encoding=text_encoding) as f:
                f.write(ass_text)

    class RecorderDanmuFetcher(DouyinLiveWebFetcher):
        def _sendHeartbeat(self):
            while record_name in recording and not is_stop_requested(record_url):
                try:
                    heartbeat = PushFrame(payload_type='hb').SerializeToString()
                    self.ws.send(heartbeat, websocket.ABNF.OPCODE_PING)
                except Exception:
                    break
                time.sleep(5)
            self.stop()

        def _wsOnOpen(self, ws):
            heartbeat_thread = threading.Thread(target=self._sendHeartbeat, daemon=True)
            heartbeat_thread.start()

        def _wsOnError(self, ws, error):
            if record_name in recording and not is_stop_requested(record_url):
                logger.debug(f"{record_name} 抖音弹幕连接错误: {error}")

        def _wsOnClose(self, ws, *args):
            self.stop()

        def _parseChatMsg(self, payload):
            try:
                message = ChatMessage().parse(payload)
                user = getattr(message, "user", None)
                self.chat_callback({
                    "user_id": str(getattr(user, "display_id", "") or getattr(user, "id", "")),
                    "nick_name": str(getattr(user, "nick_name", "") or ""),
                    "content": str(getattr(message, "content", "") or ""),
                })
            except Exception as e:
                logger.debug(f"{record_name} 解析抖音弹幕失败: {e}")

    fetcher = RecorderDanmuFetcher(live_id or room_id, chat_callback=write_chat)
    setattr(fetcher, "_DouyinLiveWebFetcher__room_id", str(room_id))

    def stop_when_recording_ends() -> None:
        while record_name in recording and not is_stop_requested(record_url):
            time.sleep(1)
        fetcher.stop()

    threading.Thread(target=stop_when_recording_ends, daemon=True).start()
    try:
        logger.info(f"{record_name} 开始录制抖音弹幕: {subtitle_file} / {ass_subtitle_file}")
        fetcher.start()
    except Exception as e:
        if record_name in recording and not is_stop_requested(record_url):
            logger.error(f"{record_name} 抖音弹幕录制失败: {e}")


def subtitle_content_mode() -> str:
    mode = str(globals().get("subtitle_content_type", "弹幕") or "弹幕").strip()
    return mode if mode in ("弹幕", "时间") else "弹幕"


def parse_yes_no(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in YES_VALUES:
        return True
    if text in NO_VALUES:
        return False
    return None


def enabled_text(value: bool) -> str:
    return "是" if value else ""


def context_bool(context: dict[str, Any] | None, key: str) -> bool:
    if not context:
        return False
    value = context.get(key)
    if isinstance(value, bool):
        return value
    return parse_yes_no(value) is True


def parse_room_flag_part(part: str) -> tuple[str, bool] | None:
    match = re.match(r"^([^:：]{1,12})\s*[:：]\s*(.+)$", str(part or "").strip())
    if not match:
        return None
    key = ROOM_FLAG_LABELS.get(match.group(1).strip())
    value = parse_yes_no(match.group(2))
    if not key or value is None:
        return None
    return key, value


def parse_room_option_part(part: str) -> tuple[str, int | str] | None:
    text = str(part or "").strip()
    priority = ROOM_STAR_PRIORITY_ALIASES.get(text)
    if priority:
        return "priority", priority
    if text in ROOM_PRIORITY_PRESETS:
        return "priority", text

    match = re.match(r"^([^:：]{1,12})\s*[:：]\s*(.+)$", text)
    if not match:
        return None
    key = ROOM_OPTION_LABELS.get(match.group(1).strip())
    if not key:
        return None

    raw_value = match.group(2).strip()
    if key == "priority":
        priority = ROOM_STAR_PRIORITY_ALIASES.get(raw_value)
        if not priority and raw_value in ROOM_PRIORITY_PRESETS:
            priority = raw_value
        if not priority:
            return None
        return key, priority

    try:
        value = int(float(raw_value))
    except ValueError:
        return None
    if key == "check_interval":
        return key, max(1, value)
    if key == "check_jitter":
        return key, max(0, value)
    return None


def room_timing_from_priority(priority: str) -> tuple[int | None, int | None]:
    if not priority:
        return None, None
    return ROOM_PRIORITY_PRESETS.get(priority, (None, None))


def build_subtitle_context(platform: str, record_url: str, stream_info: dict[str, Any]) -> dict[str, str]:
    stream_info = stream_info or {}
    return {
        "platform": platform or "",
        "record_url": record_url or "",
        "room_id": str(stream_info.get("room_id") or stream_info.get("id_str") or stream_info.get("id") or ""),
        "live_id": douyin_live_id_from_url(record_url),
    }


def start_subtitle_recorder(
        record_name: str,
        record_url: str,
        save_file_path: str,
        save_type: str,
        subtitle_context: dict[str, str] | None = None,
) -> None:
    subtitle_context = subtitle_context or {}
    room_subtitle_enabled = (
        context_bool(subtitle_context, "record_subtitle")
        or context_bool(subtitle_context, "burn_subtitle")
    )
    if not (
        globals().get("create_subtitle_file", globals().get("create_time_file", False))
        or globals().get("burn_subtitle_to_video", False)
        or room_subtitle_enabled
    ):
        return
    if '音频' in save_type:
        return

    subs_file_path = normalize_subtitle_base_path(save_file_path)
    mode = subtitle_content_mode()
    thread_prefix = "danmu" if mode == "弹幕" else "subs"
    subs_thread_name = f'{thread_prefix}_{Path(subs_file_path).name}'
    existing_thread = create_var.get(subs_thread_name)
    if isinstance(existing_thread, threading.Thread) and existing_thread.is_alive():
        return

    if mode == "弹幕":
        platform_name = subtitle_context.get("platform", "")
        if platform_name != "抖音直播":
            logger.warning(f"{record_name} 弹幕录制目前仅支持抖音直播，已跳过")
            return
        room_id = subtitle_context.get("room_id", "")
        live_id = subtitle_context.get("live_id", "")
        create_var[subs_thread_name] = threading.Thread(
            target=generate_douyin_danmu_subtitles,
            args=(record_name, record_url, room_id, live_id, subs_file_path),
            daemon=True,
        )
    else:
        if split_by_time:
            return
        create_var[subs_thread_name] = threading.Thread(
            target=generate_subtitles, args=(record_name, subs_file_path), daemon=True
        )
    create_var[subs_thread_name].start()


def adjust_max_request() -> None:
    global max_request, error_count, pre_max_request, error_window
    preset = max_request

    while True:
        time.sleep(get_request_adjust_interval_seconds())
        with max_request_lock:
            if error_window:
                error_rate = sum(error_window) / len(error_window)
            else:
                error_rate = 0

            if error_rate > error_threshold:
                max_request = max(1, max_request - 1)
            elif error_rate < error_threshold / 2 and max_request < preset:
                max_request += 1
            else:
                pass

            if pre_max_request != max_request:
                pre_max_request = max_request
                print(f"\r同一时间访问网络的线程数动态改为 {max_request}")

            error_window.append(error_count)
            if len(error_window) > error_window_size:
                error_window.pop(0)
            error_count = 0


def parse_tg_chat_ids(*values: Any) -> set[str]:
    chat_ids: set[str] = set()
    for value in values:
        for item in re.split(r"[,，;\s]+", str(value or "")):
            item = item.strip()
            if item:
                chat_ids.add(item)
    return chat_ids


def load_tg_interaction_config() -> dict[str, Any]:
    parser = configparser.RawConfigParser()
    parser.read(config_file, encoding=text_encoding)
    if not parser.has_section("推送配置"):
        return {
            "enabled": False,
            "token": "",
            "allowed_chat_ids": set(),
            "owner": "",
            "default_quality": globals().get("video_record_quality", "原画"),
        }
    token = str(
        parser.get("推送配置", "tg bot token", fallback="")
        or parser.get("推送配置", "tgapi令牌", fallback="")
        or ""
    ).strip()
    push_chat_id = str(parser.get("推送配置", "tg聊天id(个人或者群组id)", fallback="") or "").strip()
    allowed_chat_id_text = str(parser.get("推送配置", "tg机器人允许聊天id(逗号分隔)", fallback="") or "").strip()
    owner = parse_room_owner_part(
        f"用户: {parser.get('推送配置', 'tg添加直播间归属用户', fallback='')}"
    ) or ""
    default_quality = str(
        parser.get("录制设置", "原画|超清|高清|标清|流畅", fallback=globals().get("video_record_quality", "原画"))
        or "原画"
    ).strip()
    return {
        "enabled": parse_yes_no(parser.get("推送配置", "tg机器人交互开启(是/否)", fallback="否")) is True,
        "token": token,
        "allowed_chat_ids": parse_tg_chat_ids(push_chat_id, allowed_chat_id_text),
        "owner": owner,
        "default_quality": default_quality,
    }


def telegram_api_request(token: str, method: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8") or "{}")
    if not result.get("ok"):
        raise RuntimeError(result.get("description") or f"Telegram API {method} failed")
    return result


def telegram_send_message(token: str, chat_id: str | int, text: str, reply_to_message_id: int | None = None) -> None:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text[:3900],
        "disable_web_page_preview": True,
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    telegram_api_request(token, "sendMessage", payload, timeout=15)


def telegram_initial_update_offset(token: str) -> int | None:
    try:
        payload = {"offset": -1, "limit": 1, "timeout": 0, "allowed_updates": ["message"]}
        result = telegram_api_request(token, "getUpdates", payload, timeout=5)
        updates = result.get("result") or []
        if updates:
            return int(updates[-1].get("update_id", 0)) + 1
    except Exception as err:
        logger.warning(f"TG机器人初始化失败: {err}")
    return None


def format_tg_room_reply(rooms: list[dict[str, Any]], owner: str = "") -> str:
    added_count = sum(1 for room in rooms if not room.get("existing"))
    updated_count = len(rooms) - added_count
    lines = [f"已处理 {len(rooms)} 个直播间：新增 {added_count}，更新 {updated_count}。"]
    if owner:
        lines.append(f"归属用户：{owner}")
    for room in rooms[:6]:
        action = "更新" if room.get("existing") else "新增"
        name = str(room.get("name") or "").strip()
        group = str(room.get("group") or "").strip()
        url = str(room.get("url") or "").strip()
        label = name or group or url
        lines.append(f"{action}：{label}")
        if url and label != url:
            lines.append(url)
    if len(rooms) > 6:
        lines.append(f"另有 {len(rooms) - 6} 个已处理。")
    lines.append("主程序会在下一次配置重载后开始监控。")
    return "\n".join(lines)


def tg_room_scope(settings: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    owner = str(settings.get("owner") or "").strip()
    rooms = read_rooms(url_config_file, text_encoding, str(settings.get("default_quality") or "原画"))
    if owner:
        rooms = [room for room in rooms if str(room.get("owner") or "") == owner]
    return sorted(rooms, key=lambda room: int(room.get("id", 0))), owner


def tg_room_label(room: dict[str, Any]) -> str:
    name = str(room.get("name") or "").strip()
    group = str(room.get("group") or "").strip()
    url = str(room.get("url") or "").strip()
    return name or group or url or "未命名直播间"


def tg_parse_list_args(args: str) -> tuple[int, str]:
    text = str(args or "").strip()
    if not text:
        return 1, ""
    match = re.match(r"^(?:p|page|第)?\s*(\d+)\s*(?:页)?$", text, re.IGNORECASE)
    if match:
        return max(1, int(match.group(1))), ""
    match = re.match(r"^(?:p|page|第)?\s*(\d+)\s*(?:页)?\s+(.+)$", text, re.IGNORECASE)
    if match:
        return max(1, int(match.group(1))), match.group(2).strip()
    return 1, text


def tg_format_room_list(rooms: list[dict[str, Any]], owner: str = "", args: str = "") -> str:
    page, keyword = tg_parse_list_args(args)
    indexed_rooms = list(enumerate(rooms, start=1))
    if keyword:
        lowered = keyword.lower()
        indexed_rooms = [
            (number, room) for number, room in indexed_rooms
            if lowered in tg_room_label(room).lower()
            or lowered in str(room.get("group") or "").lower()
            or lowered in str(room.get("url") or "").lower()
        ]
    if not indexed_rooms:
        return "没有匹配的直播间。" if keyword else "暂无直播间。"

    page_size = 20
    page_count = max(1, (len(indexed_rooms) + page_size - 1) // page_size)
    page = min(page, page_count)
    start = (page - 1) * page_size
    visible_rooms = indexed_rooms[start:start + page_size]

    lines = [f"直播间列表（{len(indexed_rooms)} 个，第 {page}/{page_count} 页）"]
    if keyword:
        lines.append(f"筛选：{keyword}")
    if owner:
        lines.append(f"归属用户：{owner}")
    for number, room in visible_rooms:
        state = "启用" if room.get("enabled", True) else "停用"
        group = str(room.get("group") or "").strip() or "未分组"
        lines.append(f"{number}. [{state}] {tg_room_label(room)} / {group}")
        lines.append(str(room.get("url") or ""))
    if page_count > 1:
        if page < page_count:
            lines.append(f"下一页：/list {page + 1}{(' ' + keyword) if keyword else ''}")
        lines.append("删除/启停可直接用全局序号，例如 /del 34、/off 34")
    return "\n".join(lines)


def tg_select_room(selector: str, settings: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    rooms, _owner = tg_room_scope(settings)
    selector = str(selector or "").strip()
    if not selector:
        return None, "请提供直播间序号、链接或关键词。"

    if selector.isdigit():
        index = int(selector) - 1
        if 0 <= index < len(rooms):
            return rooms[index], ""
        return None, f"序号不存在，当前共有 {len(rooms)} 个直播间。"

    target_url = normalize_url(selector) if "://" in selector else ""
    if target_url:
        for room in rooms:
            if normalize_url(str(room.get("url") or "")) == target_url:
                return room, ""
        return None, "没有找到这个链接对应的直播间。"

    lowered = selector.lower()
    matches = [
        room for room in rooms
        if lowered in tg_room_label(room).lower()
        or lowered in str(room.get("group") or "").lower()
        or lowered in str(room.get("url") or "").lower()
    ]
    if not matches:
        return None, "没有找到匹配的直播间。"
    if len(matches) > 1:
        preview = "\n".join(
            f"{rooms.index(room) + 1}. {tg_room_label(room)}"
            for room in matches[:8]
        )
        return None, f"匹配到多个直播间，请用序号操作：\n{preview}"
    return matches[0], ""


def tg_room_id(room: dict[str, Any]) -> int:
    return int(room.get("id", -1))


def tg_handle_room_command(command: str, args: str, settings: dict[str, Any]) -> str | None:
    if command in ("/list", "/rooms", "/roomlist"):
        rooms, owner = tg_room_scope(settings)
        return tg_format_room_list(rooms, owner, args.strip())

    if command in ("/add", "/new"):
        if not args.strip():
            return "用法：/add 直播间链接或分享文案"
        return "__ADD_ROOM__"

    if command in ("/del", "/delete", "/remove"):
        room, error = tg_select_room(args, settings)
        if not room:
            return error
        delete_room(url_config_file, text_encoding, tg_room_id(room), file_update_lock)
        return f"已删除：{tg_room_label(room)}"

    if command in ("/on", "/enable"):
        room, error = tg_select_room(args, settings)
        if not room:
            return error
        updated = patch_rooms(
            url_config_file,
            text_encoding,
            [tg_room_id(room)],
            {"enabled": True},
            str(settings.get("default_quality") or "原画"),
            file_update_lock,
        )
        return f"已启用：{tg_room_label(updated[0] if updated else room)}"

    if command in ("/off", "/disable"):
        room, error = tg_select_room(args, settings)
        if not room:
            return error
        updated = patch_rooms(
            url_config_file,
            text_encoding,
            [tg_room_id(room)],
            {"enabled": False},
            str(settings.get("default_quality") or "原画"),
            file_update_lock,
        )
        return f"已停用：{tg_room_label(updated[0] if updated else room)}"

    return None


def handle_tg_interaction_update(update: dict[str, Any], settings: dict[str, Any]) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    text = str(message.get("text") or message.get("caption") or "").strip()
    message_id = message.get("message_id")
    token = str(settings.get("token") or "")
    if not chat_id or not token or not text:
        return

    command_text, _space, args = text.partition(" ")
    lowered = command_text.lower()
    command = lowered.split("@", 1)[0]
    if command in ("/chatid", "/chat_id"):
        telegram_send_message(token, chat_id, f"当前 chat_id：{chat_id}", message_id)
        return

    if chat_id not in settings.get("allowed_chat_ids", set()):
        return

    if command in ("/start", "/help"):
        telegram_send_message(
            token,
            chat_id,
            "直接发送直播间链接或手机端分享文案即可添加直播间。\n"
            "命令：\n"
            "/list [页码|关键词] 查看直播间\n"
            "/add 链接 添加直播间\n"
            "/del 序号|链接|关键词 删除直播间\n"
            "/on 序号|链接|关键词 启用直播间\n"
            "/off 序号|链接|关键词 停用直播间\n"
            "/chatid 查看当前聊天 ID\n"
            "多页列表可用 /list 2 查看第 2 页，删除可直接用列表里的全局序号，例如 /del 34。\n"
            "添加时也支持：分组: 名称、主播: 名称、字幕: 是、烧录: 是、★★★。",
            message_id,
        )
        return

    try:
        command_reply = tg_handle_room_command(command, args, settings)
        if command_reply and command_reply != "__ADD_ROOM__":
            telegram_send_message(token, chat_id, command_reply, message_id)
            return
        add_text = args if command_reply == "__ADD_ROOM__" else text
        owner = str(settings.get("owner") or "")
        rooms = append_rooms(
            url_config_file,
            text_encoding,
            add_text,
            str(settings.get("default_quality") or "原画"),
            file_update_lock,
            owner=owner,
        )
        if not rooms:
            telegram_send_message(token, chat_id, "没有识别到有效直播间链接。", message_id)
            return
        warning_lines = []
        if owner:
            for room in rooms:
                url = str(room.get("url") or "")
                if url and not user_has_record_permission(user_config_file, owner, url):
                    warning_lines.append(f"{owner} 无权录制 {permission_site_name(detect_permission_site(url))}")
        reply = format_tg_room_reply(rooms, owner)
        if warning_lines:
            reply = f"{reply}\n\n注意：{'；'.join(sorted(set(warning_lines)))}"
        telegram_send_message(token, chat_id, reply, message_id)
        print(f"TG机器人已添加或更新 {len(rooms)} 个直播间")
    except Exception as err:
        logger.error(f"TG机器人添加直播间失败: {err}")
        telegram_send_message(token, chat_id, f"添加失败：{err}", message_id)


def tg_interaction_loop() -> None:
    offset: int | None = None
    active_token = ""
    announced = False
    while True:
        settings = load_tg_interaction_config()
        token = str(settings.get("token") or "")
        if not settings.get("enabled") or not token:
            announced = False
            time.sleep(TG_INTERACTION_RETRY_SECONDS)
            continue

        if token != active_token:
            offset = telegram_initial_update_offset(token)
            active_token = token

        if not announced:
            print("TG机器人交互已启动，可直接向机器人发送直播链接添加直播间")
            announced = True

        try:
            payload = {
                "timeout": TG_INTERACTION_POLL_TIMEOUT_SECONDS,
                "allowed_updates": ["message"],
            }
            if offset is not None:
                payload["offset"] = offset
            result = telegram_api_request(
                token,
                "getUpdates",
                payload,
                timeout=TG_INTERACTION_POLL_TIMEOUT_SECONDS + 10,
            )
            for update in result.get("result") or []:
                update_id = int(update.get("update_id", 0))
                offset = max(offset or 0, update_id + 1)
                handle_tg_interaction_update(update, settings)
        except Exception as err:
            logger.warning(f"TG机器人轮询失败: {err}")
            time.sleep(TG_INTERACTION_RETRY_SECONDS)


def start_tg_interaction_bot() -> None:
    global tg_interaction_started
    with tg_interaction_lock:
        if tg_interaction_started:
            return
        thread = threading.Thread(target=tg_interaction_loop, name="tg-interaction-bot", daemon=True)
        thread.start()
        tg_interaction_started = True


def push_message(record_name: str, live_url: str, content: str) -> None:
    msg_title = push_message_title.strip() or "直播间状态更新通知"
    push_functions = {
        '微信': lambda: xizhi(xizhi_api_url, msg_title, content),
        '钉钉': lambda: dingtalk(dingtalk_api_url, content, dingtalk_phone_num, dingtalk_is_atall),
        '邮箱': lambda: send_email(
            email_host, login_email, email_password, sender_email, sender_name,
            to_email, msg_title, content, smtp_port, open_smtp_ssl
        ),
        'TG': lambda: tg_bot(tg_chat_id, tg_token, content),
        'BARK': lambda: bark(
            bark_msg_api, title=msg_title, content=content, level=bark_msg_level, sound=bark_msg_ring
        ),
        'NTFY': lambda: ntfy(
            ntfy_api, title=msg_title, content=content, tags=ntfy_tags, action_url=live_url, email=ntfy_email
        ),
        'PUSHPLUS': lambda: pushplus(pushplus_token, msg_title, content),
    }

    for platform, func in push_functions.items():
        if platform in live_status_push.upper():
            try:
                result = func()
                print(f'提示信息：已经将[{record_name}]直播状态消息推送至你的{platform},'
                      f' 成功{len(result["success"])}, 失败{len(result["error"])}')
            except Exception as e:
                color_obj.print_colored(f"直播消息推送到{platform}失败: {e}", color_obj.RED)


def run_script(command: str) -> None:
    try:
        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=get_startup_info(os_type)
        )
        stdout, stderr = process.communicate()
        stdout_decoded = stdout.decode('utf-8')
        stderr_decoded = stderr.decode('utf-8')
        if stdout_decoded.strip():
            print(stdout_decoded)
        if stderr_decoded.strip():
            print(stderr_decoded)
    except PermissionError as e:
        logger.error(e)
        logger.error('脚本无执行权限!, 若是Linux环境, 请先执行:chmod +x your_script.sh 授予脚本可执行权限')
    except OSError as e:
        logger.error(e)
        logger.error('Please add `#!/bin/bash` at the beginning of your bash script file.')


def clear_record_info(record_name: str, record_url: str) -> None:
    global monitoring
    removed = False
    with webui_status_lock:
        recording.discard(record_name)
        recording_time_list.pop(record_name, None)
        if record_url in url_comments and record_url in running_list:
            running_list.remove(record_url)
            monitoring -= 1
            removed = True
    update_webui_room_status(record_url, status="disabled", record_name=record_name, message="已停用", next_check_at="")
    if removed:
        color_obj.print_colored(f"[{record_name}]已经从录制列表中移除\n", color_obj.YELLOW)


def direct_download_stream(source_url: str, save_path: str, record_name: str, live_url: str, platform: str) -> bool:
    try:
        client = httpx.Client(timeout=None)

        headers = {}
        header_params = get_record_headers(platform, live_url)
        if header_params:
            key, value = header_params.split(":", 1)
            headers[key] = value

        with client.stream('GET', source_url, headers=headers, follow_redirects=True) as response:
            if response.status_code != 200:
                logger.error(f"请求直播流失败，状态码: {response.status_code}")
                return False

            part_index = 0
            downloaded = 0
            chunk_size = parse_int_setting(
                globals().get("direct_download_chunk_kb", DEFAULT_DIRECT_DOWNLOAD_CHUNK_KB),
                DEFAULT_DIRECT_DOWNLOAD_CHUNK_KB,
                min_value=16,
                max_value=4096,
            ) * 1024
            current_save_path = size_split_file_path(save_path, part_index)
            f = open(current_save_path, 'wb')

            try:
                for chunk in response.iter_bytes(chunk_size):
                    if is_stop_requested(live_url):
                        color_obj.print_colored(f"[{record_name}]录制时已被注释或请求停止,下载中断", color_obj.YELLOW)
                        clear_record_info(record_name, live_url)
                        return False

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if should_split_by_size(current_save_path):
                            f.close()
                            part_index += 1
                            downloaded = 0
                            mark_size_split(live_url)
                            update_webui_room_status(
                                live_url,
                                status="recording",
                                record_name=record_name,
                                message="达到分段大小，继续写入下一段",
                            )
                            current_save_path = size_split_file_path(save_path, part_index)
                            f = open(current_save_path, 'wb')
                print()
                return True
            finally:
                if not f.closed:
                    f.close()
    except Exception as e:
        logger.error(f"FLV下载错误: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
        return False


def check_subprocess(record_name: str, record_url: str, ffmpeg_command: list, save_type: str,
                     script_command: str | None = None,
                     subtitle_context: dict[str, str] | None = None) -> bool | str:
    save_file_path = ffmpeg_command[-1]
    process = subprocess.Popen(
        ffmpeg_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=get_startup_info(os_type),
    )
    register_active_record_output(save_file_path)
    size_limit_reached = False

    start_subtitle_recorder(record_name, record_url, save_file_path, save_type, subtitle_context)

    while process.poll() is None:
        if is_stop_requested(record_url):
            color_obj.print_colored(f"[{record_name}]录制时已被注释,本条线程将会退出", color_obj.YELLOW)
            clear_record_info(record_name, record_url)
            update_webui_room_status(record_url, status="stopped", record_name=record_name, message="录制已停止")
            stop_record_process(process)
            process.wait()
            unregister_active_record_output(save_file_path)
            return True
        if should_split_by_size(save_file_path):
            size_limit_reached = True
            mark_size_split(record_url)
            update_webui_room_status(
                record_url,
                status="recording",
                record_name=record_name,
                message="达到分段大小，准备继续录制下一段",
            )
            stop_record_process(process)
            process.wait()
            break
        time.sleep(record_process_check_seconds())

    return_code = process.returncode
    if size_limit_reached:
        return_code = 0
    stop_time = time.strftime('%Y-%m-%d %H:%M:%S')
    if return_code == 0:
        if size_limit_reached:
            update_webui_room_status(
                record_url,
                status="recording",
                record_name=record_name,
                message="达到分段大小，继续录制下一段",
            )
        else:
            update_webui_room_status(record_url, status="finished", record_name=record_name, message="录制完成")
        burn_subtitle_for_record = context_bool(subtitle_context, "burn_subtitle")
        if (converts_to_mp4 or burn_subtitle_for_record) and save_type == 'TS':
            if split_by_time:
                start_segment_mp4_conversions(save_file_path, delete_origin_file, burn_subtitle_for_record)
            else:
                start_mp4_conversion(save_file_path, delete_origin_file, burn_subtitle_for_record)
        if size_limit_reached:
            print(f"\n{record_name} {stop_time} 已达到分段大小，继续录制下一段\n")
        else:
            print(f"\n{record_name} {stop_time} 直播录制完成\n")

        if script_command and not size_limit_reached:
            logger.debug("开始执行脚本命令!")
            if "python" in script_command:
                params = [
                    f'--record_name "{record_name}"',
                    f'--save_file_path "{save_file_path}"',
                    f'--save_type {save_type}',
                    f'--split_video_by_time {split_video_by_time}',
                    f'--converts_to_mp4 {converts_to_mp4}',
                ]
            else:
                params = [
                    f'"{record_name.split(" ", maxsplit=1)[-1]}"',
                    f'"{save_file_path}"',
                    save_type,
                    f'split_video_by_time:{split_video_by_time}',
                    f'converts_to_mp4:{converts_to_mp4}'
                ]
            script_command = script_command.strip() + ' ' + ' '.join(params)
            run_script(script_command)
            logger.debug("脚本命令执行结束!")

    else:
        color_obj.print_colored(f"\n{record_name} {stop_time} 直播录制出错,返回码: {return_code}\n", color_obj.RED)
        update_webui_room_status(
            record_url,
            status="error",
            record_name=record_name,
            message=f"录制出错,返回码: {return_code}"
        )

    if return_code == 0:
        record_history_from_active(record_name, record_url)
    mark_recording_stopped(record_name)
    unregister_active_record_output(save_file_path)
    if size_limit_reached:
        return SIZE_SPLIT_RESULT
    return False


def clean_name(input_text):
    cleaned_name = re.sub(rstr, "_", input_text.strip()).strip('_')
    cleaned_name = cleaned_name.replace("（", "(").replace("）", ")")
    if clean_emoji:
        cleaned_name = utils.remove_emojis(cleaned_name, '_').strip('_')
    return cleaned_name or '空白昵称'


def get_quality_code(qn):
    QUALITY_MAPPING = {
        "原画": "OD",
        "蓝光": "BD",
        "超清": "UHD",
        "高清": "HD",
        "标清": "SD",
        "流畅": "LD"
    }
    return QUALITY_MAPPING.get(qn)


def get_record_headers(platform, live_url):
    live_domain = '/'.join(live_url.split('/')[0:3])
    record_headers = {
        'PandaTV': 'origin:https://www.pandalive.co.kr',
        'WinkTV': 'origin:https://www.winktv.co.kr',
        'PopkonTV': 'origin:https://www.popkontv.com',
        'FlexTV': 'origin:https://www.flextv.co.kr',
        '千度热播': 'referer:https://qiandurebo.com',
        '17Live': 'referer:https://17.live/en/live/6302408',
        '浪Live': 'referer:https://www.lang.live',
        'shopee': f'origin:{live_domain}',
        'Blued直播': 'referer:https://app.blued.cn',
        'xHamsterLive': f'referer:{live_domain}',
    }
    return record_headers.get(platform)


def is_flv_preferred_platform(link):
    return any(i in link for i in ["douyin", "tiktok"])


def select_source_url(link, stream_info):
    if is_flv_preferred_platform(link):
        codec = utils.get_query_params(stream_info.get('flv_url'), "codec")
        if codec and codec[0] == 'h265':
            logger.warning("FLV is not supported for h265 codec, use HLS source instead")
        else:
            return stream_info.get('flv_url')

    return stream_info.get('record_url')


def start_record(url_data: tuple, count_variable: int = -1) -> None:
    global error_count

    while True:
        try:
            record_url = url_data[1]
            with room_dispatch_lock:
                worker_state = dict(room_worker_states.get(record_url, {}))
            record_finished = bool(worker_state.get("record_finished", False))
            run_once = bool(worker_state.get("run_once", False))
            start_pushed = bool(worker_state.get("start_pushed", False))
            new_record_url = str(worker_state.get("new_record_url", ""))
            count_time = float(worker_state.get("count_time", time.time()))
            retry = 0
            record_quality_zh, record_url, anchor_name = url_data[:3]
            configured_anchor_name = anchor_name
            room_record_subtitle = bool(url_data[3]) if len(url_data) > 3 else False
            room_burn_subtitle = bool(url_data[4]) if len(url_data) > 4 else False
            room_check_interval = url_data[5] if len(url_data) > 5 else None
            room_check_jitter = url_data[6] if len(url_data) > 6 else None
            room_priority = str(url_data[7]) if len(url_data) > 7 else ""
            room_group = clean_room_group(url_data[8]) if len(url_data) > 8 else infer_room_group(record_url)
            room_owner = str(url_data[9]) if len(url_data) > 9 else ""
            priority_interval, priority_jitter = room_timing_from_priority(room_priority)
            room_check_interval = room_check_interval or priority_interval
            room_check_jitter = room_check_jitter if room_check_jitter is not None else priority_jitter
            burn_subtitle_for_room = room_burn_subtitle or bool(globals().get("burn_subtitle_to_video", False))
            record_quality = get_quality_code(record_quality_zh)
            proxy_address = proxy_addr
            platform = '未知平台'
            live_domain = '/'.join(record_url.split('/')[0:3])
            update_webui_room_status(
                record_url,
                status="checking",
                quality=record_quality_zh,
                configured_name=anchor_name,
                configured_group=room_group,
                group=room_group,
                owner=room_owner,
                platform=platform,
                message="检测直播间",
                next_check_at="",
            )

            if proxy_addr:
                proxy_address = None
                for platform in enable_proxy_platform_list:
                    if platform and platform.strip() in record_url:
                        proxy_address = proxy_addr
                        break

            if not proxy_address:
                if extra_enable_proxy_platform_list:
                    for pt in extra_enable_proxy_platform_list:
                        if pt and pt.strip() in record_url:
                            proxy_address = proxy_addr_bak or None

            # print(f'\r代理地址:{proxy_address}')
            # print(f'\r全局代理:{global_proxy}')
            while True:
                try:
                    port_info = []
                    if record_url.find("douyin.com/") > -1:
                        platform = '抖音直播'
                        with semaphore:
                            if 'v.douyin.com' not in record_url and '/user/' not in record_url:
                                json_data = asyncio.run(spider.get_douyin_web_stream_data(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=dy_cookie))
                            else:
                                json_data = asyncio.run(spider.get_douyin_app_stream_data(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=dy_cookie))
                            port_info = asyncio.run(
                                stream.get_douyin_stream_url(json_data, record_quality, proxy_address))

                    elif record_url.find("https://www.tiktok.com/") > -1:
                        platform = 'TikTok直播'
                        with semaphore:
                            if global_proxy or proxy_address:
                                json_data = asyncio.run(spider.get_tiktok_stream_data(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=tiktok_cookie))
                                port_info = asyncio.run(
                                    stream.get_tiktok_stream_url(json_data, record_quality, proxy_address))
                            else:
                                logger.error("错误信息: 网络异常，请检查网络是否能正常访问TikTok平台")

                    elif record_url.find("https://live.kuaishou.com/") > -1:
                        platform = '快手直播'
                        with semaphore:
                            json_data = asyncio.run(spider.get_kuaishou_stream_data(
                                url=record_url,
                                proxy_addr=proxy_address,
                                cookies=ks_cookie))
                            port_info = asyncio.run(stream.get_kuaishou_stream_url(json_data, record_quality))

                    elif record_url.find("https://www.huya.com/") > -1:
                        platform = '虎牙直播'
                        with semaphore:
                            if record_quality not in ['OD', 'BD', 'UHD']:
                                json_data = asyncio.run(spider.get_huya_stream_data(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=hy_cookie))
                                port_info = asyncio.run(stream.get_huya_stream_url(json_data, record_quality))
                            else:
                                port_info = asyncio.run(spider.get_huya_app_stream_url(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=hy_cookie
                                ))

                    elif record_url.find("https://www.douyu.com/") > -1:
                        platform = '斗鱼直播'
                        with semaphore:
                            json_data = asyncio.run(spider.get_douyu_info_data(
                                url=record_url, proxy_addr=proxy_address, cookies=douyu_cookie))
                            port_info = asyncio.run(stream.get_douyu_stream_url(
                                json_data, video_quality=record_quality, cookies=douyu_cookie, proxy_addr=proxy_address
                            ))

                    elif record_url.find("https://www.yy.com/") > -1:
                        platform = 'YY直播'
                        with semaphore:
                            json_data = asyncio.run(spider.get_yy_stream_data(
                                url=record_url, proxy_addr=proxy_address, cookies=yy_cookie))
                            port_info = asyncio.run(stream.get_yy_stream_url(json_data))

                    elif record_url.find("https://live.bilibili.com/") > -1:
                        platform = 'B站直播'
                        with semaphore:
                            json_data = asyncio.run(spider.get_bilibili_room_info(
                                url=record_url, proxy_addr=proxy_address, cookies=bili_cookie))
                            port_info = asyncio.run(stream.get_bilibili_stream_url(
                                json_data, video_quality=record_quality, cookies=bili_cookie, proxy_addr=proxy_address))

                    elif record_url.find("http://xhslink.com/") > -1 or \
                            record_url.find("https://www.xiaohongshu.com/") > -1:
                        platform = '小红书直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_xhs_stream_url(
                                record_url, proxy_addr=proxy_address, cookies=xhs_cookie))
                            retry += 1

                    elif record_url.find("www.bigo.tv/") > -1 or record_url.find("slink.bigovideo.tv/") > -1:
                        platform = 'Bigo直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_bigo_stream_url(
                                record_url, proxy_addr=proxy_address, cookies=bigo_cookie))

                    elif record_url.find("https://app.blued.cn/") > -1:
                        platform = 'Blued直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_blued_stream_url(
                                record_url, proxy_addr=proxy_address, cookies=blued_cookie))

                    elif record_url.find("sooplive.co.kr/") > -1 or record_url.find("sooplive.com/") > -1:
                        platform = 'SOOP'
                        with semaphore:
                            if global_proxy or proxy_address:
                                json_data = asyncio.run(spider.get_sooplive_stream_data(
                                    url=record_url, proxy_addr=proxy_address,
                                    cookies=sooplive_cookie,
                                    username=sooplive_username,
                                    password=sooplive_password
                                ))
                                if json_data and json_data.get('new_cookies'):
                                    utils.update_config(
                                        config_file, 'Cookie', 'sooplive_cookie', json_data['new_cookies']
                                    )
                                port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))
                            else:
                                logger.error("错误信息: 网络异常，请检查本网络是否能正常访问SOOP平台")

                    elif record_url.find("cc.163.com/") > -1:
                        platform = '网易CC直播'
                        with semaphore:
                            json_data = asyncio.run(spider.get_netease_stream_data(
                                url=record_url, cookies=netease_cookie))
                            port_info = asyncio.run(stream.get_netease_stream_url(json_data, record_quality))

                    elif record_url.find("qiandurebo.com/") > -1:
                        platform = '千度热播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_qiandurebo_stream_data(
                                url=record_url, proxy_addr=proxy_address, cookies=qiandurebo_cookie))

                    elif record_url.find("www.pandalive.co.kr/") > -1:
                        platform = 'PandaTV'
                        with semaphore:
                            if global_proxy or proxy_address:
                                json_data = asyncio.run(spider.get_pandatv_stream_data(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=pandatv_cookie
                                ))
                                port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))
                            else:
                                logger.error("错误信息: 网络异常，请检查本网络是否能正常访问PandaTV直播平台")

                    elif record_url.find("fm.missevan.com/") > -1:
                        platform = '猫耳FM直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_maoerfm_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=maoerfm_cookie))

                    elif record_url.find("www.winktv.co.kr/") > -1:
                        platform = 'WinkTV'
                        with semaphore:
                            if global_proxy or proxy_address:
                                json_data = asyncio.run(spider.get_winktv_stream_data(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=winktv_cookie))
                                port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))
                            else:
                                logger.error("错误信息: 网络异常，请检查本网络是否能正常访问WinkTV直播平台")

                    elif record_url.find("www.flextv.co.kr/") > -1 or record_url.find("www.ttinglive.com/") > -1:
                        platform = 'FlexTV'
                        with semaphore:
                            if global_proxy or proxy_address:
                                json_data = asyncio.run(spider.get_flextv_stream_data(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=flextv_cookie,
                                    username=flextv_username,
                                    password=flextv_password
                                ))
                                if json_data and json_data.get('new_cookies'):
                                    utils.update_config(
                                        config_file, 'Cookie', 'flextv_cookie', json_data['new_cookies']
                                    )
                                if 'play_url_list' in json_data:
                                    port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))
                                else:
                                    port_info = json_data
                            else:
                                logger.error("错误信息: 网络异常，请检查本网络是否能正常访问FlexTV直播平台")

                    elif record_url.find("look.163.com/") > -1:
                        platform = 'Look直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_looklive_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=look_cookie
                            ))

                    elif record_url.find("www.popkontv.com/") > -1:
                        platform = 'PopkonTV'
                        with semaphore:
                            if global_proxy or proxy_address:
                                port_info = asyncio.run(spider.get_popkontv_stream_url(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    access_token=popkontv_access_token,
                                    username=popkontv_username,
                                    password=popkontv_password,
                                    partner_code=popkontv_partner_code
                                ))
                                if port_info and port_info.get('new_token'):
                                    utils.update_config(
                                        file_path=config_file, section='Authorization', key='popkontv_token',
                                        new_value=port_info['new_token']
                                    )

                            else:
                                logger.error("错误信息: 网络异常，请检查本网络是否能正常访问PopkonTV直播平台")

                    elif record_url.find("twitcasting.tv/") > -1:
                        platform = 'TwitCasting'
                        with semaphore:
                            json_data = asyncio.run(spider.get_twitcasting_stream_url(
                                url=record_url,
                                proxy_addr=proxy_address,
                                cookies=twitcasting_cookie,
                                account_type=twitcasting_account_type,
                                username=twitcasting_username,
                                password=twitcasting_password
                            ))
                            port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=False))

                            if port_info and port_info.get('new_cookies'):
                                utils.update_config(
                                    file_path=config_file, section='Cookie', key='twitcasting_cookie',
                                    new_value=port_info['new_cookies']
                                )

                    elif record_url.find("live.baidu.com/") > -1:
                        platform = '百度直播'
                        with semaphore:
                            json_data = asyncio.run(spider.get_baidu_stream_data(
                                url=record_url,
                                proxy_addr=proxy_address,
                                cookies=baidu_cookie))
                            port_info = asyncio.run(stream.get_stream_url(json_data, record_quality))

                    elif record_url.find("weibo.com/") > -1:
                        platform = '微博直播'
                        with semaphore:
                            json_data = asyncio.run(spider.get_weibo_stream_data(
                                url=record_url, proxy_addr=proxy_address, cookies=weibo_cookie))
                            port_info = asyncio.run(stream.get_stream_url(
                                json_data, record_quality, hls_extra_key='m3u8_url'))

                    elif record_url.find("kugou.com/") > -1:
                        platform = '酷狗直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_kugou_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=kugou_cookie))

                    elif record_url.find("www.twitch.tv/") > -1:
                        platform = 'TwitchTV'
                        with semaphore:
                            if global_proxy or proxy_address:
                                json_data = asyncio.run(spider.get_twitchtv_stream_data(
                                    url=record_url,
                                    proxy_addr=proxy_address,
                                    cookies=twitch_cookie
                                ))
                                port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))
                            else:
                                logger.error("错误信息: 网络异常，请检查本网络是否能正常访问TwitchTV直播平台")

                    elif record_url.find("www.liveme.com/") > -1:
                        if global_proxy or proxy_address:
                            platform = 'LiveMe'
                            with semaphore:
                                port_info = asyncio.run(spider.get_liveme_stream_url(
                                    url=record_url, proxy_addr=proxy_address, cookies=liveme_cookie))
                        else:
                            logger.error("错误信息: 网络异常，请检查本网络是否能正常访问LiveMe直播平台")

                    elif record_url.find("www.huajiao.com/") > -1:
                        platform = '花椒直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_huajiao_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=huajiao_cookie))

                    elif record_url.find("7u66.com/") > -1:
                        platform = '流星直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_liuxing_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=liuxing_cookie))

                    elif record_url.find("showroom-live.com/") > -1:
                        platform = 'ShowRoom'
                        with semaphore:
                            json_data = asyncio.run(spider.get_showroom_stream_data(
                                url=record_url, proxy_addr=proxy_address, cookies=showroom_cookie))
                            port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))

                    elif record_url.find("live.acfun.cn/") > -1 or record_url.find("m.acfun.cn/") > -1:
                        platform = 'Acfun'
                        with semaphore:
                            json_data = asyncio.run(spider.get_acfun_stream_data(
                                url=record_url, proxy_addr=proxy_address, cookies=acfun_cookie))
                            port_info = asyncio.run(stream.get_stream_url(
                                json_data, record_quality, url_type='flv', flv_extra_key='url'))

                    elif record_url.find("live.tlclw.com/") > -1:
                        platform = '畅聊直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_changliao_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=changliao_cookie))

                    elif record_url.find("ybw1666.com/") > -1:
                        platform = '音播直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_yinbo_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=yinbo_cookie))

                    elif record_url.find("www.inke.cn/") > -1:
                        platform = '映客直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_yingke_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=yingke_cookie))

                    elif record_url.find("www.zhihu.com/") > -1:
                        platform = '知乎直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_zhihu_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=zhihu_cookie))

                    elif record_url.find("chzzk.naver.com/") > -1:
                        platform = 'CHZZK'
                        with semaphore:
                            json_data = asyncio.run(spider.get_chzzk_stream_data(
                                url=record_url, proxy_addr=proxy_address, cookies=chzzk_cookie))
                            port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))

                    elif record_url.find("www.haixiutv.com/") > -1:
                        platform = '嗨秀直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_haixiu_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=haixiu_cookie))

                    elif record_url.find("vvxqiu.com/") > -1:
                        platform = 'VV星球'
                        with semaphore:
                            port_info = asyncio.run(spider.get_vvxqiu_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=vvxqiu_cookie))

                    elif record_url.find("17.live/") > -1:
                        platform = '17Live'
                        with semaphore:
                            port_info = asyncio.run(spider.get_17live_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=yiqilive_cookie))

                    elif record_url.find("www.lang.live/") > -1:
                        platform = '浪Live'
                        with semaphore:
                            port_info = asyncio.run(spider.get_langlive_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=langlive_cookie))

                    elif record_url.find("m.pp.weimipopo.com/") > -1:
                        platform = '漂漂直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_pplive_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=pplive_cookie))

                    elif record_url.find(".6.cn/") > -1:
                        platform = '六间房直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_6room_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=six_room_cookie))

                    elif record_url.find("lehaitv.com/") > -1:
                        platform = '乐嗨直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_haixiu_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=lehaitv_cookie))

                    elif record_url.find("h.catshow168.com/") > -1:
                        platform = '花猫直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_pplive_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=huamao_cookie))

                    elif record_url.find("live.shopee") > -1 or record_url.find("shp.ee/") > -1:
                        platform = 'shopee'
                        with semaphore:
                            port_info = asyncio.run(spider.get_shopee_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=shopee_cookie))
                            if port_info.get('uid'):
                                new_record_url = record_url.split('?')[0] + '?' + str(port_info['uid'])

                    elif record_url.find("www.youtube.com/") > -1 or record_url.find("youtu.be/") > -1:
                        platform = 'Youtube'
                        with semaphore:
                            json_data = asyncio.run(spider.get_youtube_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=youtube_cookie))
                            port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))

                    elif record_url.find("xhamsterlive.com/") > -1:
                        platform = 'xHamsterLive'
                        with semaphore:
                            json_data = asyncio.run(spider.get_xhamsterlive_stream_url(
                                url=record_url, proxy_addr=proxy_address))
                            if json_data.get('play_url_list'):
                                port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))
                            else:
                                port_info = json_data

                    elif record_url.find("tb.cn") > -1:
                        platform = '淘宝直播'
                        with semaphore:
                            json_data = asyncio.run(spider.get_taobao_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=taobao_cookie))
                            port_info = asyncio.run(stream.get_stream_url(
                                json_data, record_quality,
                                url_type='all', hls_extra_key='hlsUrl', flv_extra_key='flvUrl'
                            ))

                    elif record_url.find("3.cn") > -1 or record_url.find("m.jd.com") > -1:
                        platform = '京东直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_jd_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=jd_cookie))

                    elif record_url.find("faceit.com/") > -1:
                        platform = 'faceit'
                        with semaphore:
                            if global_proxy or proxy_address:
                                with semaphore:
                                    json_data = asyncio.run(spider.get_faceit_stream_data(
                                        url=record_url, proxy_addr=proxy_address, cookies=faceit_cookie))
                                    port_info = asyncio.run(stream.get_stream_url(json_data, record_quality, spec=True))
                            else:
                                logger.error("错误信息: 网络异常，请检查本网络是否能正常访问faceit直播平台")

                    elif record_url.find("www.miguvideo.com") > -1 or record_url.find("m.miguvideo.com") > -1:
                        platform = '咪咕直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_migu_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=migu_cookie))

                    elif record_url.find("show.lailianjie.com") > -1:
                        platform = '连接直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_lianjie_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=lianjie_cookie))

                    elif record_url.find("www.imkktv.com") > -1:
                        platform = '来秀直播'
                        with semaphore:
                            port_info = asyncio.run(spider.get_laixiu_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=laixiu_cookie))

                    elif record_url.find("www.picarto.tv") > -1:
                        platform = 'Picarto'
                        with semaphore:
                            port_info = asyncio.run(spider.get_picarto_stream_url(
                                url=record_url, proxy_addr=proxy_address, cookies=picarto_cookie))

                    elif record_url.find(".m3u8") > -1 or record_url.find(".flv") > -1:
                        platform = '自定义录制直播'
                        port_info = {
                            "anchor_name": platform + '_' + str(uuid.uuid4())[:8],
                            "is_live": True,
                            "record_url": record_url,
                        }
                        if '.flv' in record_url:
                            port_info['flv_url'] = record_url
                        else:
                            port_info['m3u8_url'] = record_url

                    else:
                        logger.error(f'{record_url} {platform}直播地址')
                        update_webui_room_status(record_url, status="error", platform=platform, message="未知直播地址")
                        return

                    if anchor_name:
                        if '主播:' in anchor_name:
                            anchor_split: list = anchor_name.split('主播:')
                            if len(anchor_split) > 1 and anchor_split[1].strip():
                                anchor_name = anchor_split[1].strip()
                            else:
                                anchor_name = port_info.get("anchor_name", '')
                    else:
                        anchor_name = port_info.get("anchor_name", '')
                    avatar_url = port_info.get("avatar_url") or None

                    if not port_info.get("anchor_name", ''):
                        print(f'序号{count_variable} 网址内容获取失败,进行重试中...获取失败的地址是:{url_data}')
                        update_webui_room_status(
                            record_url,
                            status="error",
                            platform=platform,
                            quality=record_quality_zh,
                            message="网址内容获取失败",
                        )
                        add_instant_error()
                    else:
                        anchor_name = clean_name(anchor_name)
                        record_name = f'序号{count_variable} {anchor_name}'
                        update_webui_room_status(
                            record_url,
                            status="checking",
                            platform=platform,
                            anchor_name=anchor_name,
                            avatar_url=avatar_url,
                            record_name=record_name,
                            quality=record_quality_zh,
                        )

                        if is_stop_requested(record_url):
                            print(f"[{anchor_name}]已被注释,本条线程将会退出")
                            clear_record_info(record_name, record_url)
                            return

                        if not configured_anchor_name and run_once is False:
                            if new_record_url:
                                need_update_line_list.append(
                                    f'{record_url}|{new_record_url},主播: {anchor_name.strip()}')
                                not_record_list.append(new_record_url)
                            else:
                                need_update_line_list.append(f'{record_url}|{record_url},主播: {anchor_name.strip()}')
                            run_once = True

                        push_at = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
                        if port_info['is_live'] is False:
                            waiting_message = port_info.get("message") or "等待直播"
                            print(f"\r{record_name} {waiting_message}... ")
                            update_webui_room_status(
                                record_url,
                                status="waiting",
                                platform=platform,
                                anchor_name=anchor_name,
                                avatar_url=avatar_url,
                                record_name=record_name,
                                quality=record_quality_zh,
                                message=waiting_message,
                            )

                            if start_pushed:
                                if over_show_push:
                                    push_content = "直播间状态更新：[直播间名称] 直播已结束！时间：[时间]"
                                    if over_push_message_text:
                                        push_content = over_push_message_text

                                    push_content = (push_content.replace('[直播间名称]', record_name).
                                                    replace('[时间]', push_at))
                                    threading.Thread(
                                        target=push_message,
                                        args=(record_name, record_url, push_content.replace(r'\n', '\n')),
                                        daemon=True
                                    ).start()
                                start_pushed = False

                        else:
                            content = f"\r{record_name} 正在直播中..."
                            print(content)
                            update_webui_room_status(
                                record_url,
                                status="live",
                                platform=platform,
                                anchor_name=anchor_name,
                                avatar_url=avatar_url,
                                record_name=record_name,
                                quality=record_quality_zh,
                                message="正在直播",
                            )

                            if live_status_push and not start_pushed:
                                if begin_show_push:
                                    push_content = "直播间状态更新：[直播间名称] 正在直播中，时间：[时间]"
                                    if begin_push_message_text:
                                        push_content = begin_push_message_text

                                    push_content = (push_content.replace('[直播间名称]', record_name).
                                                    replace('[时间]', push_at))
                                    threading.Thread(
                                        target=push_message,
                                        args=(record_name, record_url, push_content.replace(r'\n', '\n')),
                                        daemon=True
                                    ).start()
                                start_pushed = True

                            if disable_record:
                                update_webui_room_status(
                                    record_url,
                                    status="waiting",
                                    platform=platform,
                                    anchor_name=anchor_name,
                                    avatar_url=avatar_url,
                                    record_name=record_name,
                                    quality=record_quality_zh,
                                    message="只推送不录制",
                                )
                                persist_room_worker_state(
                                    record_url, record_finished, run_once, start_pushed, new_record_url, count_time
                                )
                                schedule_room_check(record_url, push_check_seconds)
                                return

                            real_url = select_source_url(record_url, port_info)
                            full_path = f'{default_path}/{platform}'
                            if real_url:
                                now = current_record_time_text()
                                live_title = port_info.get('title')
                                title_in_name = ''
                                if live_title:
                                    live_title = clean_name(live_title)
                                    title_in_name = live_title + '_' if filename_by_title else ''

                                try:
                                    if len(video_save_path) > 0:
                                        if not video_save_path.endswith(('/', '\\')):
                                            full_path = f'{video_save_path}/{platform}'
                                        else:
                                            full_path = f'{video_save_path}{platform}'

                                    full_path = full_path.replace("\\", '/')
                                    if folder_by_author:
                                        full_path = f'{full_path}/{anchor_name}'
                                    if folder_by_time:
                                        full_path = f'{full_path}/{now[:10]}'
                                    if folder_by_title and port_info.get('title'):
                                        if folder_by_time:
                                            full_path = f'{full_path}/{live_title}_{anchor_name}'
                                        else:
                                            full_path = f'{full_path}/{now[:10]}_{live_title}'
                                    if not os.path.exists(full_path):
                                        os.makedirs(full_path)
                                except Exception as e:
                                    logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")

                                if platform != '自定义录制直播':
                                    if enable_https_recording and real_url.startswith("http://"):
                                        real_url = real_url.replace("http://", "https://")

                                    http_record_list = ['shopee', "migu"]
                                    if platform in http_record_list:
                                        real_url = real_url.replace("https://", "http://")

                                user_agent = ("Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 ("
                                              "KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile "
                                              "Safari/537.36")

                                rw_timeout = "15000000"
                                analyzeduration = "5000000"
                                probesize = "2000000"
                                bufsize = "2000k"
                                max_muxing_queue_size = "256"
                                for pt_host in overseas_platform_host:
                                    if pt_host in record_url:
                                        rw_timeout = "50000000"
                                        analyzeduration = "10000000"
                                        probesize = "5000000"
                                        bufsize = "4000k"
                                        max_muxing_queue_size = "512"
                                        break

                                ffmpeg_command = [
                                    'ffmpeg', "-y",
                                    "-nostats",
                                    "-rw_timeout", rw_timeout,
                                    "-loglevel", "error",
                                    "-hide_banner",
                                    "-user_agent", user_agent,
                                    "-protocol_whitelist", "rtmp,crypto,file,http,https,tcp,tls,udp,rtp,httpproxy",
                                    "-thread_queue_size", "128",
                                    "-analyzeduration", analyzeduration,
                                    "-probesize", probesize,
                                    "-fflags", "+discardcorrupt",
                                    "-re", "-i", real_url,
                                    *ffmpeg_thread_args(),
                                    "-bufsize", bufsize,
                                    "-sn", "-dn",
                                    "-reconnect_delay_max", "60",
                                    "-reconnect_streamed", "-reconnect_at_eof",
                                    "-max_muxing_queue_size", max_muxing_queue_size,
                                    "-correct_ts_overflow", "1",
                                    "-avoid_negative_ts", "1"
                                ]

                                headers = get_record_headers(platform, record_url)
                                if headers:
                                    insert_before_input(ffmpeg_command, "-headers", headers)

                                if proxy_address:
                                    insert_before_input(ffmpeg_command, "-http_proxy", proxy_address)

                                start_record_time = mark_recording_started(record_name, record_quality_zh)
                                update_webui_room_status(
                                    record_url,
                                    status="recording",
                                    platform=platform,
                                    anchor_name=anchor_name,
                                    avatar_url=avatar_url,
                                    record_name=record_name,
                                    quality=record_quality_zh,
                                    save_path=full_path,
                                    started_at=start_record_time.isoformat(timespec="seconds"),
                                    message="录制中",
                                    next_check_at="",
                                )
                                rec_info = f"\r{anchor_name} 准备开始录制视频: {full_path}"
                                if show_url:
                                    re_plat = ('WinkTV', 'PandaTV', 'ShowRoom', 'CHZZK', 'Youtube')
                                    if platform in re_plat:
                                        logger.info(
                                            f"{platform} | {anchor_name} | 直播源地址: {port_info.get('m3u8_url')}")
                                    else:
                                        logger.info(
                                            f"{platform} | {anchor_name} | 直播源地址: {real_url}")

                                only_flv_record = False
                                only_flv_platform_list = ['shopee', '花椒直播']
                                if platform in only_flv_platform_list:
                                    logger.debug(f"提示: {platform} 将强制使用FLV格式录制")
                                    only_flv_record = True

                                only_audio_record = False
                                only_audio_platform_list = ['猫耳FM直播', 'Look直播']
                                if platform in only_audio_platform_list:
                                    only_audio_record = True

                                record_save_type = video_save_type
                                subtitle_context = build_subtitle_context(platform, record_url, port_info)
                                subtitle_context["record_subtitle"] = enabled_text(room_record_subtitle)
                                subtitle_context["burn_subtitle"] = enabled_text(room_burn_subtitle)

                                if is_flv_preferred_platform(record_url) and port_info.get('flv_url'):
                                    codec = utils.get_query_params(port_info['flv_url'], "codec")
                                    if codec and codec[0] == 'h265':
                                        logger.warning("FLV is not supported for h265 codec, use TS format instead")
                                        record_save_type = "TS"

                                if only_audio_record or any(i in record_save_type for i in ['MP3', 'M4A']):
                                    try:
                                        now = current_record_time_text()
                                        extension = "mp3" if "m4a" not in record_save_type.lower() else "m4a"
                                        name_format = "_%03d" if split_by_time else ""
                                        save_file_path = (f"{full_path}/{anchor_name}_{title_in_name}{now}"
                                                          f"{name_format}.{extension}")

                                        if split_by_time:
                                            print(f'\r{anchor_name} 准备开始录制音频: {save_file_path}')

                                            if "MP3" in record_save_type:
                                                command = [
                                                    "-map", "0:a",
                                                    "-c:a", "libmp3lame",
                                                    "-ab", "320k",
                                                    "-f", "segment",
                                                    "-segment_time", split_time,
                                                    "-reset_timestamps", "1",
                                                    save_file_path,
                                                ]
                                            else:
                                                command = [
                                                    "-map", "0:a",
                                                    "-c:a", "aac",
                                                    "-bsf:a", "aac_adtstoasc",
                                                    "-ab", "320k",
                                                    "-f", "segment",
                                                    "-segment_time", split_time,
                                                    "-segment_format", 'mpegts',
                                                    "-reset_timestamps", "1",
                                                    save_file_path,
                                                ]

                                        else:
                                            if "MP3" in record_save_type:
                                                command = [
                                                    "-map", "0:a",
                                                    "-c:a", "libmp3lame",
                                                    "-ab", "320k",
                                                    save_file_path,
                                                ]

                                            else:
                                                command = [
                                                    "-map", "0:a",
                                                    "-c:a", "aac",
                                                    "-bsf:a", "aac_adtstoasc",
                                                    "-ab", "320k",
                                                    "-movflags", "+faststart",
                                                    save_file_path,
                                                ]

                                        ffmpeg_command.extend(command)
                                        comment_end = check_subprocess(
                                            record_name,
                                            record_url,
                                            ffmpeg_command,
                                            record_save_type,
                                            custom_script,
                                            subtitle_context,
                                        )
                                        if comment_end and comment_end != SIZE_SPLIT_RESULT:
                                            return

                                    except subprocess.CalledProcessError as e:
                                        logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                                        add_instant_error()

                                if only_flv_record:
                                    logger.info(f"Use Direct Downloader to Download FLV Stream: {record_url}")
                                    filename = anchor_name + f'_{title_in_name}' + now + '.flv'
                                    save_file_path = f'{full_path}/{filename}'
                                    print(f'{rec_info}/{filename}')

                                    try:
                                        flv_url = port_info.get('flv_url')
                                        if flv_url:
                                            start_record_time = mark_recording_started(record_name, record_quality_zh)
                                            start_subtitle_recorder(
                                                record_name,
                                                record_url,
                                                save_file_path,
                                                record_save_type,
                                                subtitle_context,
                                            )

                                            download_success = direct_download_stream(
                                                flv_url, save_file_path, record_name, record_url, platform
                                            )

                                            if download_success:
                                                record_finished = True
                                                update_webui_room_status(
                                                    record_url,
                                                    status="finished",
                                                    platform=platform,
                                                    anchor_name=anchor_name,
                                                    record_name=record_name,
                                                    message="录制完成",
                                                )
                                                print(
                                                    f"\n{anchor_name} {time.strftime('%Y-%m-%d %H:%M:%S')} 直播录制完成\n")
                                                record_history_from_active(record_name, record_url)

                                            mark_recording_stopped(record_name)
                                        else:
                                            logger.debug("未找到FLV直播流，跳过录制")
                                            update_webui_room_status(
                                                record_url,
                                                status="error",
                                                platform=platform,
                                                anchor_name=anchor_name,
                                                record_name=record_name,
                                                message="未找到FLV直播流",
                                            )
                                    except Exception as e:
                                        clear_record_info(record_name, record_url)
                                        color_obj.print_colored(
                                            f"\n{anchor_name} {time.strftime('%Y-%m-%d %H:%M:%S')} 直播录制出错,请检查网络\n",
                                            color_obj.RED)
                                        update_webui_room_status(
                                            record_url,
                                            status="error",
                                            platform=platform,
                                            anchor_name=anchor_name,
                                            record_name=record_name,
                                            message="录制出错",
                                        )
                                        logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                                        add_instant_error()

                                elif record_save_type == "FLV":
                                    filename = anchor_name + f'_{title_in_name}' + now + ".flv"
                                    print(f'{rec_info}/{filename}')
                                    save_file_path = full_path + '/' + filename

                                    try:
                                        if split_by_time:
                                            now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
                                            save_file_path = f"{full_path}/{anchor_name}_{title_in_name}{now}_%03d.flv"
                                            command = [
                                                "-map", "0",
                                                "-c:v", "copy",
                                                "-c:a", "copy",
                                                "-bsf:a", "aac_adtstoasc",
                                                "-f", "segment",
                                                "-segment_time", split_time,
                                                "-segment_format", "flv",
                                                "-reset_timestamps", "1",
                                                save_file_path
                                            ]

                                        else:
                                            command = [
                                                "-map", "0",
                                                "-c:v", "copy",
                                                "-c:a", "copy",
                                                "-bsf:a", "aac_adtstoasc",
                                                "-f", "flv",
                                                "{path}".format(path=save_file_path),
                                            ]
                                        ffmpeg_command.extend(command)

                                        comment_end = check_subprocess(
                                            record_name,
                                            record_url,
                                            ffmpeg_command,
                                            record_save_type,
                                            custom_script,
                                            subtitle_context,
                                        )
                                        if comment_end and comment_end != SIZE_SPLIT_RESULT:
                                            return

                                    except subprocess.CalledProcessError as e:
                                        logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                                        add_instant_error()

                                    try:
                                        if converts_to_mp4 or burn_subtitle_for_room:
                                            seg_file_path = f"{full_path}/{anchor_name}_{title_in_name}{now}_%03d.mp4"
                                            if split_by_time and burn_subtitle_for_room:
                                                start_segment_mp4_conversions(
                                                    save_file_path, delete_origin_file, burn_subtitle_for_room
                                                )
                                            elif split_by_time:
                                                segment_video(
                                                    save_file_path, seg_file_path,
                                                    segment_format='mp4', segment_time=split_time,
                                                    is_original_delete=delete_origin_file
                                                )
                                            else:
                                                start_mp4_conversion(save_file_path, delete_origin_file, burn_subtitle_for_room)

                                        else:
                                            seg_file_path = f"{full_path}/{anchor_name}_{title_in_name}{now}_%03d.flv"
                                            if split_by_time:
                                                segment_video(
                                                    save_file_path, seg_file_path,
                                                    segment_format='flv', segment_time=split_time,
                                                    is_original_delete=delete_origin_file
                                                )
                                    except Exception as e:
                                        logger.error(f"转码失败: {e} ")

                                elif record_save_type == "MKV":
                                    filename = anchor_name + f'_{title_in_name}' + now + ".mkv"
                                    print(f'{rec_info}/{filename}')
                                    save_file_path = full_path + '/' + filename

                                    try:
                                        if split_by_time:
                                            now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
                                            save_file_path = f"{full_path}/{anchor_name}_{title_in_name}{now}_%03d.mkv"
                                            command = [
                                                "-flags", "global_header",
                                                "-c:v", "copy",
                                                "-c:a", "aac",
                                                "-map", "0",
                                                "-f", "segment",
                                                "-segment_time", split_time,
                                                "-segment_format", "matroska",
                                                "-reset_timestamps", "1",
                                                save_file_path,
                                            ]

                                        else:
                                            command = [
                                                "-flags", "global_header",
                                                "-map", "0",
                                                "-c:v", "copy",
                                                "-c:a", "copy",
                                                "-f", "matroska",
                                                "{path}".format(path=save_file_path),
                                            ]
                                        ffmpeg_command.extend(command)

                                        comment_end = check_subprocess(
                                            record_name,
                                            record_url,
                                            ffmpeg_command,
                                            record_save_type,
                                            custom_script,
                                            subtitle_context,
                                        )
                                        if comment_end and comment_end != SIZE_SPLIT_RESULT:
                                            return

                                    except subprocess.CalledProcessError as e:
                                        logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                                        add_instant_error()

                                elif record_save_type == "MP4":
                                    filename = anchor_name + f'_{title_in_name}' + now + ".mp4"
                                    print(f'{rec_info}/{filename}')
                                    mp4_file_path = full_path + '/' + filename

                                    try:
                                        if split_by_time:
                                            now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
                                            save_file_path = f"{full_path}/{anchor_name}_{title_in_name}{now}_%03d.ts"
                                            command = [
                                                "-c:v", "copy",
                                                "-c:a", "copy",
                                                "-map", "0",
                                                "-f", "segment",
                                                "-segment_time", split_time,
                                                "-segment_format", "mpegts",
                                                "-reset_timestamps", "1",
                                                save_file_path,
                                            ]

                                        else:
                                            save_file_path = mp4_file_path.rsplit('.', maxsplit=1)[0] + ".ts"
                                            command = [
                                                "-map", "0",
                                                "-c:v", "copy",
                                                "-c:a", "copy",
                                                "-f", "mpegts",
                                                save_file_path,
                                            ]

                                        ffmpeg_command.extend(command)
                                        comment_end = check_subprocess(
                                            record_name,
                                            record_url,
                                            ffmpeg_command,
                                            record_save_type,
                                            custom_script,
                                            subtitle_context,
                                        )
                                        if split_by_time:
                                            start_segment_mp4_conversions(save_file_path, True, burn_subtitle_for_room)
                                        else:
                                            start_mp4_conversion(save_file_path, True, burn_subtitle_for_room)
                                        if comment_end and comment_end != SIZE_SPLIT_RESULT:
                                            return

                                    except subprocess.CalledProcessError as e:
                                        logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                                        add_instant_error()

                                else:
                                    if split_by_time:
                                        now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
                                        filename = anchor_name + f'_{title_in_name}' + now + ".ts"
                                        print(f'{rec_info}/{filename}')

                                        try:
                                            save_file_path = f"{full_path}/{anchor_name}_{title_in_name}{now}_%03d.ts"
                                            command = [
                                                "-c:v", "copy",
                                                "-c:a", "copy",
                                                "-map", "0",
                                                "-f", "segment",
                                                "-segment_time", split_time,
                                                "-segment_format", 'mpegts',
                                                "-reset_timestamps", "1",
                                                save_file_path,
                                            ]

                                            ffmpeg_command.extend(command)
                                            comment_end = check_subprocess(
                                                record_name,
                                                record_url,
                                                ffmpeg_command,
                                                record_save_type,
                                                custom_script,
                                                subtitle_context,
                                            )
                                            if comment_end:
                                                if converts_to_mp4 or burn_subtitle_for_room:
                                                    start_segment_mp4_conversions(
                                                        save_file_path, delete_origin_file, burn_subtitle_for_room
                                                    )
                                                if comment_end != SIZE_SPLIT_RESULT:
                                                    return

                                        except subprocess.CalledProcessError as e:
                                            logger.error(
                                                f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                                            add_instant_error()

                                    else:
                                        filename = anchor_name + f'_{title_in_name}' + now + ".ts"
                                        print(f'{rec_info}/{filename}')
                                        save_file_path = full_path + '/' + filename

                                        try:
                                            command = [
                                                "-c:v", "copy",
                                                "-c:a", "copy",
                                                "-map", "0",
                                                "-f", "mpegts",
                                                save_file_path,
                                            ]

                                            ffmpeg_command.extend(command)
                                            comment_end = check_subprocess(
                                                record_name,
                                                record_url,
                                                ffmpeg_command,
                                                record_save_type,
                                                custom_script,
                                                subtitle_context,
                                            )
                                            if comment_end:
                                                if (converts_to_mp4 or burn_subtitle_for_room) and comment_end != SIZE_SPLIT_RESULT:
                                                    start_mp4_conversion(
                                                        save_file_path, delete_origin_file, burn_subtitle_for_room
                                                    )
                                                if comment_end != SIZE_SPLIT_RESULT:
                                                    return

                                        except subprocess.CalledProcessError as e:
                                            logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                                            add_instant_error()

                                count_time = time.time()

                except Exception as e:
                    logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
                    update_webui_room_status(
                        record_url,
                        status="error",
                        platform=platform,
                        quality=record_quality_zh,
                        message=str(e),
                    )
                    add_instant_error()

                runtime_interval, runtime_jitter = get_room_runtime_timing(record_url)
                delay_seconds = int(runtime_interval or room_check_interval or delay_default)
                if runtime_jitter is not None:
                    jitter_seconds = int(runtime_jitter)
                elif room_check_jitter is not None:
                    jitter_seconds = int(room_check_jitter)
                else:
                    jitter_seconds = loop_random_jitter_seconds()
                num = random.randint(-jitter_seconds, jitter_seconds) + delay_seconds
                if num < 0:
                    num = 0
                x = num

                # 这里是.如果录制结束后,循环时间会暂时变成30s后检测一遍. 这样一定程度上防止主播卡顿造成少录
                # 当30秒过后检测一遍后. 会回归正常设置的循环秒数
                if consume_size_split(record_url):
                    x = 0
                elif record_finished:
                    count_time_end = time.time() - count_time
                    if count_time_end < 60:
                        x = 30
                    record_finished = False

                else:
                    x = apply_error_backoff_delay(num)

                persist_room_worker_state(
                    record_url, record_finished, run_once, start_pushed, new_record_url, count_time
                )
                schedule_room_check(record_url, x)
                return
        except Exception as e:
            logger.error(f"错误信息: {e} 发生错误的行数: {e.__traceback__.tb_lineno}")
            if 'record_url' in locals():
                update_webui_room_status(
                    record_url,
                    status="error",
                    platform=locals().get("platform", "未知平台"),
                    message=str(e),
                )
            add_instant_error()
            if 'record_url' in locals():
                schedule_room_check(record_url, 2)
            return


def backup_file(file_path: str, backup_dir_path: str, limit_counts: int = 6) -> None:
    try:
        if not os.path.exists(backup_dir_path):
            os.makedirs(backup_dir_path)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_file_name = os.path.basename(file_path) + '_' + timestamp
        backup_file_path = os.path.join(backup_dir_path, backup_file_name).replace("\\", "/")
        shutil.copy2(file_path, backup_file_path)

        files = os.listdir(backup_dir_path)
        _files = [f for f in files if f.startswith(os.path.basename(file_path))]
        _files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir_path, x)))

        while len(_files) > limit_counts:
            oldest_file = _files[0]
            os.remove(os.path.join(backup_dir_path, oldest_file))
            _files = _files[1:]

    except Exception as e:
        logger.error(f'\r备份配置文件 {file_path} 失败：{str(e)}')


def backup_file_start() -> None:
    config_md5 = ''
    url_config_md5 = ''

    while True:
        try:
            if os.path.exists(config_file):
                new_config_md5 = utils.check_md5(config_file)
                if new_config_md5 != config_md5:
                    backup_file(config_file, backup_dir)
                    config_md5 = new_config_md5

            if os.path.exists(url_config_file):
                new_url_config_md5 = utils.check_md5(url_config_file)
                if new_url_config_md5 != url_config_md5:
                    backup_file(url_config_file, backup_dir)
                    url_config_md5 = new_url_config_md5
            time.sleep(600)
        except Exception as e:
            logger.error(f"备份配置文件失败, 错误信息: {e}")


def check_ffmpeg_existence() -> bool:
    try:
        result = subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            version_line = lines[0]
            built_line = lines[1]
            print(version_line)
            print(built_line)
    except subprocess.CalledProcessError as e:
        logger.error(e)
    except FileNotFoundError:
        pass
    finally:
        if check_ffmpeg():
            time.sleep(1)
            return True
    return False


# --------------------------初始化程序-------------------------------------
print("-----------------------------------------------------")
print("|                DouyinLiveRecorder                 |")
print("-----------------------------------------------------")

print(f"版本号: {version}")
print("GitHub: https://github.com/ihmily/DouyinLiveRecorder")
print(f'支持平台: {platforms}')
print('.....................................................')
if not check_ffmpeg_existence():
    logger.error("缺少ffmpeg无法进行录制，程序退出")
    sys.exit(1)
os.makedirs(os.path.dirname(config_file), exist_ok=True)
t3 = threading.Thread(target=backup_file_start, args=(), daemon=True)
t3.start()
Path(url_config_file).touch(exist_ok=True)
utils.remove_duplicate_lines(url_config_file)


def read_config_value(config_parser: configparser.RawConfigParser, section: str, option: str, default_value: Any) \
        -> Any:
    try:

        config_parser.read(config_file, encoding=text_encoding)
        if '录制设置' not in config_parser.sections():
            config_parser.add_section('录制设置')
        if '推送配置' not in config_parser.sections():
            config_parser.add_section('推送配置')
        if 'Cookie' not in config_parser.sections():
            config_parser.add_section('Cookie')
        if 'Authorization' not in config_parser.sections():
            config_parser.add_section('Authorization')
        if '账号密码' not in config_parser.sections():
            config_parser.add_section('账号密码')
        if 'WebUI' not in config_parser.sections():
            config_parser.add_section('WebUI')
        if section not in config_parser.sections():
            config_parser.add_section(section)
        return config_parser.get(section, option)
    except (configparser.NoSectionError, configparser.NoOptionError):
        if section not in config_parser.sections():
            config_parser.add_section(section)
        config_parser.set(section, option, str(default_value))
        with open(config_file, 'w', encoding=text_encoding) as f:
            config_parser.write(f)
        return default_value


options = {"是": True, "否": False}
config = configparser.RawConfigParser()
language = read_config_value(config, '录制设置', 'language(zh_cn/en)', "zh_cn")
skip_proxy_check = options.get(read_config_value(config, '录制设置', '是否跳过代理检测(是/否)', "否"), False)
webui_enabled = options.get(read_config_value(config, 'WebUI', '是否启用WebUI(是/否)', "是"), True)
webui_host_config = read_config_value(config, 'WebUI', 'WebUI监听地址', os.getenv("WEBUI_HOST", "127.0.0.1"))
webui_host = os.getenv("WEBUI_HOST") or webui_host_config
try:
    webui_port_config = read_config_value(config, 'WebUI', 'WebUI端口', os.getenv("WEBUI_PORT", 8080))
    webui_port = int(os.getenv("WEBUI_PORT") or webui_port_config)
except ValueError:
    webui_port = 8080
legacy_webui_token = config.get('WebUI', 'WebUI访问令牌', fallback='')
webui_username_config = read_config_value(config, 'WebUI', 'WebUI登录用户名', "admin")
webui_username_override = os.getenv("WEBUI_USERNAME")
webui_username = webui_username_override.strip() if webui_username_override and webui_username_override.strip() else webui_username_config
webui_password_config = read_config_value(
    config, 'WebUI', 'WebUI登录密码', legacy_webui_token or "admin"
)
webui_password_override = os.getenv("WEBUI_PASSWORD")
webui_password = webui_password_override if webui_password_override else webui_password_config
try:
    webui_session_hours_config = read_config_value(config, 'WebUI', 'WebUI会话有效期(小时)', os.getenv("WEBUI_SESSION_HOURS", 24))
    webui_session_hours = int(os.getenv("WEBUI_SESSION_HOURS") or webui_session_hours_config)
except ValueError:
    webui_session_hours = 24
if language and 'en' not in language.lower():
    from i18n import translated_print

    builtins.print = translated_print

webui_server = None
if webui_enabled:
    try:
        webui_app = RecorderWebUI(
            config_file=config_file,
            url_config_file=url_config_file,
            user_config_file=user_config_file,
            encoding=text_encoding,
            file_lock=file_update_lock,
            status_provider=get_webui_status_snapshot,
            default_quality_provider=lambda: globals().get("video_record_quality", "原画"),
            history_provider=get_record_history_summary,
            runtime_stop_callback=request_webui_stop_urls,
            username=webui_username,
            password=webui_password,
            session_hours=webui_session_hours,
        )
        webui_server, _webui_thread = start_webui_server(webui_host, webui_port, webui_app)
        print(f"WebUI已启动: http://{webui_host}:{webui_port}")
    except OSError as err:
        logger.error(f"WebUI启动失败: {err}")

try:
    if skip_proxy_check:
        global_proxy = True
    else:
        print('系统代理检测中，请耐心等待...')
        response_g = urllib.request.urlopen("https://www.google.com/", timeout=15)
        global_proxy = True
        print('\r全局/规则网络代理已开启√')
        pd = ProxyDetector()
        if pd.is_proxy_enabled():
            proxy_info = pd.get_proxy_info()
            print("System Proxy: http://{}:{}".format(proxy_info.ip, proxy_info.port))
except HTTPError as err:
    print(f"HTTP error occurred: {err.code} - {err.reason}")
except URLError:
    color_obj.print_colored("INFO：未检测到全局/规则网络代理，请检查代理配置（若无需录制海外直播请忽略此条提示）",
                            color_obj.YELLOW)
except Exception as err:
    print("An unexpected error occurred:", err)

while True:

    try:
        if not os.path.isfile(config_file):
            with open(config_file, 'w', encoding=text_encoding) as file:
                pass

        ini_URL_content = ''
        if os.path.isfile(url_config_file):
            with open(url_config_file, 'r', encoding=text_encoding) as file:
                ini_URL_content = file.read().strip()

        if not ini_URL_content.strip():
            if webui_enabled:
                time.sleep(1)
            else:
                input_url = input('请输入要录制的主播直播间网址（尽量使用PC网页端的直播间地址）:\n')
                with open(url_config_file, 'w', encoding=text_encoding) as file:
                    file.write(input_url)
    except OSError as err:
        logger.error(f"发生 I/O 错误: {err}")

    video_save_path = read_config_value(config, '录制设置', '直播保存路径(不填则默认)', "")
    folder_by_author = options.get(read_config_value(config, '录制设置', '保存文件夹是否以作者区分', "是"), False)
    folder_by_time = options.get(read_config_value(config, '录制设置', '保存文件夹是否以时间区分', "否"), False)
    folder_by_title = options.get(read_config_value(config, '录制设置', '保存文件夹是否以标题区分', "否"), False)
    filename_by_title = options.get(read_config_value(config, '录制设置', '保存文件名是否包含标题', "否"), False)
    clean_emoji = options.get(read_config_value(config, '录制设置', '是否去除名称中的表情符号', "是"), True)
    video_save_type = read_config_value(config, '录制设置', '视频保存格式ts|mkv|flv|mp4|mp3音频|m4a音频', "mp4")
    video_record_quality = read_config_value(config, '录制设置', '原画|超清|高清|标清|流畅', "原画")
    use_proxy = options.get(read_config_value(config, '录制设置', '是否使用代理ip(是/否)', "是"), False)
    proxy_addr_bak = read_config_value(config, '录制设置', '代理地址', "")
    proxy_addr = None if not use_proxy else proxy_addr_bak
    max_request = int(read_config_value(config, '录制设置', '同一时间访问网络的线程数', 3))
    config_reload_interval_seconds = parse_int_setting(
        read_config_value(config, '录制设置', '配置文件重载间隔(秒)', DEFAULT_CONFIG_RELOAD_INTERVAL_SECONDS),
        DEFAULT_CONFIG_RELOAD_INTERVAL_SECONDS,
    )
    record_process_check_interval_seconds = parse_int_setting(
        read_config_value(config, '录制设置', '录制进程检查间隔(秒)', DEFAULT_RECORD_PROCESS_CHECK_INTERVAL_SECONDS),
        DEFAULT_RECORD_PROCESS_CHECK_INTERVAL_SECONDS,
    )
    show_status_panel = options.get(read_config_value(config, '录制设置', '是否显示状态面板(是/否)', "否"), False)
    clear_status_panel = options.get(read_config_value(config, '录制设置', '是否清屏显示状态(是/否)', "否"), False)
    status_refresh_interval_seconds = parse_int_setting(
        read_config_value(config, '录制设置', '状态面板刷新间隔(秒)', DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS),
        DEFAULT_STATUS_REFRESH_INTERVAL_SECONDS,
    )
    request_adjust_interval_seconds = parse_int_setting(
        read_config_value(config, '录制设置', '网络并发调节间隔(秒)', DEFAULT_REQUEST_ADJUST_INTERVAL_SECONDS),
        DEFAULT_REQUEST_ADJUST_INTERVAL_SECONDS,
    )
    ffmpeg_threads = parse_int_setting(
        read_config_value(config, '录制设置', 'ffmpeg使用线程数', DEFAULT_FFMPEG_THREADS),
        DEFAULT_FFMPEG_THREADS,
        min_value=1,
        max_value=16,
    )
    direct_download_chunk_kb = parse_int_setting(
        read_config_value(config, '录制设置', 'FLV下载块大小(KB)', DEFAULT_DIRECT_DOWNLOAD_CHUNK_KB),
        DEFAULT_DIRECT_DOWNLOAD_CHUNK_KB,
        min_value=16,
        max_value=4096,
    )
    semaphore = threading.Semaphore(max_request)
    delay_default = int(read_config_value(config, '录制设置', '循环时间(秒)', 120))
    loop_jitter_seconds = parse_int_setting(
        read_config_value(config, '录制设置', '循环时间随机浮动(秒)', DEFAULT_LOOP_RANDOM_JITTER_SECONDS),
        DEFAULT_LOOP_RANDOM_JITTER_SECONDS,
        min_value=0,
    )
    local_delay_default = int(read_config_value(config, '录制设置', '排队读取网址时间(秒)', 0))
    loop_time = options.get(read_config_value(config, '录制设置', '是否显示循环秒数', "否"), False)
    show_url = options.get(read_config_value(config, '录制设置', '是否显示直播源地址', "否"), False)
    split_video_by_time = options.get(read_config_value(config, '录制设置', '分段录制是否开启', "否"), False)
    split_video_mode = str(read_config_value(config, '录制设置', '视频分段模式(时间/大小)', "时间")).strip() or "时间"
    split_by_size = split_video_by_time and split_video_mode == "大小"
    split_by_time = split_video_by_time and not split_by_size
    enable_https_recording = options.get(read_config_value(config, '录制设置', '是否强制启用https录制', "否"), False)
    disk_space_limit = float(read_config_value(config, '录制设置', '录制空间剩余阈值(gb)', 1.0))
    split_time = str(read_config_value(config, '录制设置', '视频分段时间(秒)', 1800))
    split_file_size_mb = parse_split_size_mb(read_config_value(config, '录制设置', '视频分段大小(MB)', 1024))
    split_file_size_bytes = int(split_file_size_mb * 1024 * 1024)
    converts_to_mp4 = options.get(read_config_value(config, '录制设置', '录制完成后自动转为mp4格式', "否"), False)
    converts_to_h264 = options.get(read_config_value(config, '录制设置', 'mp4格式重新编码为h264', "否"), False)
    mp4_faststart = options.get(read_config_value(config, '录制设置', 'mp4是否启用faststart(是/否)', "否"), False)
    scan_orphan_ts_to_mp4 = options.get(read_config_value(config, '录制设置', '是否扫描遗留TS转MP4(是/否)', "否"), False)
    mp4_convert_concurrency = parse_int_setting(
        read_config_value(config, '录制设置', '同时转码mp4的任务数', DEFAULT_MP4_CONVERT_CONCURRENCY),
        DEFAULT_MP4_CONVERT_CONCURRENCY,
        min_value=1,
        max_value=16,
    )
    configure_mp4_convert_semaphore(mp4_convert_concurrency)
    delete_origin_file = options.get(read_config_value(config, '录制设置', '追加格式后删除原文件', "否"), False)
    legacy_subtitle_switch = read_config_value(config, '录制设置', '生成时间字幕文件', "否")
    subtitle_switch = read_config_value(config, '录制设置', '生成字幕文件', legacy_subtitle_switch)
    create_subtitle_file = options.get(subtitle_switch, False)
    create_time_file = create_subtitle_file
    subtitle_content_type = str(read_config_value(config, '录制设置', '字幕内容类型(弹幕/时间)', "弹幕")).strip() or "弹幕"
    burn_subtitle_to_video = options.get(read_config_value(config, '录制设置', '是否将字幕烧录进视频', "否"), False)
    if burn_subtitle_to_video:
        create_subtitle_file = True
        create_time_file = True
        converts_to_mp4 = True
    is_run_script = options.get(read_config_value(config, '录制设置', '是否录制完成后执行自定义脚本', "否"), False)
    custom_script = read_config_value(config, '录制设置', '自定义脚本执行命令', "") if is_run_script else None
    enable_proxy_platform = read_config_value(
        config, '录制设置', '使用代理录制的平台(逗号分隔)',
        'tiktok, soop, pandalive, winktv, flextv, popkontv, twitch, liveme, showroom, chzzk, shopee, shp, youtu, faceit'
    )
    enable_proxy_platform_list = enable_proxy_platform.replace('，', ',').split(',') if enable_proxy_platform else None
    extra_enable_proxy = read_config_value(config, '录制设置', '额外使用代理录制的平台(逗号分隔)', '')
    extra_enable_proxy_platform_list = extra_enable_proxy.replace('，', ',').split(',') if extra_enable_proxy else None
    live_status_push = read_config_value(config, '推送配置', '直播状态推送渠道', "")
    dingtalk_api_url = read_config_value(config, '推送配置', '钉钉推送接口链接', "")
    xizhi_api_url = read_config_value(config, '推送配置', '微信推送接口链接', "")
    bark_msg_api = read_config_value(config, '推送配置', 'bark推送接口链接', "")
    bark_msg_level = read_config_value(config, '推送配置', 'bark推送中断级别', "active")
    bark_msg_ring = read_config_value(config, '推送配置', 'bark推送铃声', "bell")
    dingtalk_phone_num = read_config_value(config, '推送配置', '钉钉通知@对象(填手机号)', "")
    dingtalk_is_atall = options.get(read_config_value(config, '推送配置', '钉钉通知@全体(是/否)', "否"), False)
    tg_legacy_token = config.get('推送配置', 'tgapi令牌', fallback='')
    tg_token = read_config_value(config, '推送配置', 'tg bot token', tg_legacy_token)
    tg_chat_id = read_config_value(config, '推送配置', 'tg聊天id(个人或者群组id)', "")
    tg_interaction_enabled = options.get(read_config_value(config, '推送配置', 'tg机器人交互开启(是/否)', "否"), False)
    tg_interaction_allowed_chat_ids = read_config_value(config, '推送配置', 'tg机器人允许聊天id(逗号分隔)', "")
    tg_interaction_owner = read_config_value(config, '推送配置', 'tg添加直播间归属用户', "")
    email_host = config.get('推送配置', 'SMTP邮件服务器', fallback="")
    open_smtp_ssl = options.get(config.get('推送配置', '是否使用SMTP服务SSL加密(是/否)', fallback="是"), True)
    smtp_port = config.get('推送配置', 'SMTP邮件服务器端口', fallback="")
    login_email = config.get('推送配置', '邮箱登录账号', fallback="")
    email_password = config.get('推送配置', '发件人密码(授权码)', fallback="")
    sender_email = config.get('推送配置', '发件人邮箱', fallback="")
    sender_name = config.get('推送配置', '发件人显示昵称', fallback="")
    to_email = config.get('推送配置', '收件人邮箱', fallback="")
    ntfy_api = read_config_value(config, '推送配置', 'ntfy推送地址', "")
    ntfy_tags = read_config_value(config, '推送配置', 'ntfy推送标签', "tada")
    ntfy_email = read_config_value(config, '推送配置', 'ntfy推送邮箱', "")
    pushplus_token = read_config_value(config, '推送配置', 'pushplus推送token', "")
    push_message_title = read_config_value(config, '推送配置', '自定义推送标题', "直播间状态更新通知")
    begin_push_message_text = read_config_value(config, '推送配置', '自定义开播推送内容', "")
    over_push_message_text = read_config_value(config, '推送配置', '自定义关播推送内容', "")
    disable_record = options.get(read_config_value(config, '推送配置', '只推送通知不录制(是/否)', "否"), False)
    push_check_seconds = int(read_config_value(config, '推送配置', '直播推送检测频率(秒)', 1800))
    begin_show_push = options.get(read_config_value(config, '推送配置', '开播推送开启(是/否)', "是"), True)
    over_show_push = options.get(read_config_value(config, '推送配置', '关播推送开启(是/否)', "否"), False)
    resource_alert_enabled = options.get(read_config_value(config, '推送配置', '系统资源告警开启(是/否)', "是"), True)
    resource_alert_cpu_percent = parse_float_setting(
        read_config_value(config, '推送配置', 'CPU告警阈值(%)', DEFAULT_RESOURCE_ALERT_CPU_PERCENT),
        DEFAULT_RESOURCE_ALERT_CPU_PERCENT,
        min_value=0,
        max_value=100,
    )
    resource_alert_memory_percent = parse_float_setting(
        read_config_value(config, '推送配置', '内存告警阈值(%)', DEFAULT_RESOURCE_ALERT_MEMORY_PERCENT),
        DEFAULT_RESOURCE_ALERT_MEMORY_PERCENT,
        min_value=0,
        max_value=100,
    )
    resource_alert_disk_percent = parse_float_setting(
        read_config_value(config, '推送配置', '硬盘告警阈值(%)', DEFAULT_RESOURCE_ALERT_DISK_PERCENT),
        DEFAULT_RESOURCE_ALERT_DISK_PERCENT,
        min_value=0,
        max_value=100,
    )
    resource_alert_check_seconds = parse_int_setting(
        read_config_value(config, '推送配置', '系统资源告警检测间隔(秒)', DEFAULT_RESOURCE_ALERT_CHECK_SECONDS),
        DEFAULT_RESOURCE_ALERT_CHECK_SECONDS,
        min_value=5,
    )
    resource_alert_cooldown_seconds = parse_int_setting(
        read_config_value(config, '推送配置', '系统资源告警冷却时间(秒)', DEFAULT_RESOURCE_ALERT_COOLDOWN_SECONDS),
        DEFAULT_RESOURCE_ALERT_COOLDOWN_SECONDS,
        min_value=60,
    )
    if tg_interaction_enabled and tg_token:
        start_tg_interaction_bot()
    sooplive_username = read_config_value(config, '账号密码', 'sooplive账号', '')
    sooplive_password = read_config_value(config, '账号密码', 'sooplive密码', '')
    flextv_username = read_config_value(config, '账号密码', 'flextv账号', '')
    flextv_password = read_config_value(config, '账号密码', 'flextv密码', '')
    popkontv_username = read_config_value(config, '账号密码', 'popkontv账号', '')
    popkontv_partner_code = read_config_value(config, '账号密码', 'partner_code', 'P-00001')
    popkontv_password = read_config_value(config, '账号密码', 'popkontv密码', '')
    twitcasting_account_type = read_config_value(config, '账号密码', 'twitcasting账号类型', 'normal')
    twitcasting_username = read_config_value(config, '账号密码', 'twitcasting账号', '')
    twitcasting_password = read_config_value(config, '账号密码', 'twitcasting密码', '')
    popkontv_access_token = read_config_value(config, 'Authorization', 'popkontv_token', '')
    dy_cookie = read_config_value(config, 'Cookie', '抖音cookie', '')
    ks_cookie = read_config_value(config, 'Cookie', '快手cookie', '')
    tiktok_cookie = read_config_value(config, 'Cookie', 'tiktok_cookie', '')
    hy_cookie = read_config_value(config, 'Cookie', '虎牙cookie', '')
    douyu_cookie = read_config_value(config, 'Cookie', '斗鱼cookie', '')
    yy_cookie = read_config_value(config, 'Cookie', 'yy_cookie', '')
    bili_cookie = read_config_value(config, 'Cookie', 'B站cookie', '')
    xhs_cookie = read_config_value(config, 'Cookie', '小红书cookie', '')
    bigo_cookie = read_config_value(config, 'Cookie', 'bigo_cookie', '')
    blued_cookie = read_config_value(config, 'Cookie', 'blued_cookie', '')
    sooplive_cookie = read_config_value(config, 'Cookie', 'sooplive_cookie', '')
    netease_cookie = read_config_value(config, 'Cookie', 'netease_cookie', '')
    qiandurebo_cookie = read_config_value(config, 'Cookie', '千度热播_cookie', '')
    pandatv_cookie = read_config_value(config, 'Cookie', 'pandatv_cookie', '')
    maoerfm_cookie = read_config_value(config, 'Cookie', '猫耳fm_cookie', '')
    winktv_cookie = read_config_value(config, 'Cookie', 'winktv_cookie', '')
    flextv_cookie = read_config_value(config, 'Cookie', 'flextv_cookie', '')
    look_cookie = read_config_value(config, 'Cookie', 'look_cookie', '')
    twitcasting_cookie = read_config_value(config, 'Cookie', 'twitcasting_cookie', '')
    baidu_cookie = read_config_value(config, 'Cookie', 'baidu_cookie', '')
    weibo_cookie = read_config_value(config, 'Cookie', 'weibo_cookie', '')
    kugou_cookie = read_config_value(config, 'Cookie', 'kugou_cookie', '')
    twitch_cookie = read_config_value(config, 'Cookie', 'twitch_cookie', '')
    liveme_cookie = read_config_value(config, 'Cookie', 'liveme_cookie', '')
    huajiao_cookie = read_config_value(config, 'Cookie', 'huajiao_cookie', '')
    liuxing_cookie = read_config_value(config, 'Cookie', 'liuxing_cookie', '')
    showroom_cookie = read_config_value(config, 'Cookie', 'showroom_cookie', '')
    acfun_cookie = read_config_value(config, 'Cookie', 'acfun_cookie', '')
    changliao_cookie = read_config_value(config, 'Cookie', 'changliao_cookie', '')
    yinbo_cookie = read_config_value(config, 'Cookie', 'yinbo_cookie', '')
    yingke_cookie = read_config_value(config, 'Cookie', 'yingke_cookie', '')
    zhihu_cookie = read_config_value(config, 'Cookie', 'zhihu_cookie', '')
    chzzk_cookie = read_config_value(config, 'Cookie', 'chzzk_cookie', '')
    haixiu_cookie = read_config_value(config, 'Cookie', 'haixiu_cookie', '')
    vvxqiu_cookie = read_config_value(config, 'Cookie', 'vvxqiu_cookie', '')
    yiqilive_cookie = read_config_value(config, 'Cookie', '17live_cookie', '')
    langlive_cookie = read_config_value(config, 'Cookie', 'langlive_cookie', '')
    pplive_cookie = read_config_value(config, 'Cookie', 'pplive_cookie', '')
    six_room_cookie = read_config_value(config, 'Cookie', '6room_cookie', '')
    lehaitv_cookie = read_config_value(config, 'Cookie', 'lehaitv_cookie', '')
    huamao_cookie = read_config_value(config, 'Cookie', 'huamao_cookie', '')
    shopee_cookie = read_config_value(config, 'Cookie', 'shopee_cookie', '')
    youtube_cookie = read_config_value(config, 'Cookie', 'youtube_cookie', '')
    taobao_cookie = read_config_value(config, 'Cookie', 'taobao_cookie', '')
    jd_cookie = read_config_value(config, 'Cookie', 'jd_cookie', '')
    faceit_cookie = read_config_value(config, 'Cookie', 'faceit_cookie', '')
    migu_cookie = read_config_value(config, 'Cookie', 'migu_cookie', '')
    lianjie_cookie = read_config_value(config, 'Cookie', 'lianjie_cookie', '')
    laixiu_cookie = read_config_value(config, 'Cookie', 'laixiu_cookie', '')
    picarto_cookie = read_config_value(config, 'Cookie', 'picarto_cookie', '')

    video_save_type_list = ("FLV", "MKV", "TS", "MP4", "MP3音频", "M4A音频", "MP3", "M4A")
    if video_save_type and video_save_type.upper() in video_save_type_list:
        video_save_type = video_save_type.upper()
    else:
        video_save_type = "TS"
    start_ts_conversion_scanner()
    maybe_send_system_resource_alert()

    check_path = video_save_path or default_path
    if utils.check_disk_capacity(check_path, show=first_run) < disk_space_limit:
        exit_recording = True
        if not recording:
            logger.warning(f"Disk space remaining is below {disk_space_limit} GB. "
                           f"Exiting program due to the disk space limit being reached.")
            sys.exit(-1)


    def contains_url(string: str) -> bool:
        pattern = r"(https?://)?(www\.)?[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+(:\d+)?(/.*)?"
        return re.search(pattern, string) is not None


    try:
        url_comments, line_list, url_line_list = [[] for _ in range(3)]
        with (open(url_config_file, "r", encoding=text_encoding, errors='ignore') as file):
            for origin_line in file:
                if origin_line in line_list:
                    delete_line(url_config_file, origin_line)
                line_list.append(origin_line)
                line = origin_line.strip()
                if len(line) < 18:
                    continue

                line_spilt = line.split('主播: ')
                if len(line_spilt) > 2:
                    line = update_file(url_config_file, line, f'{line_spilt[0]}主播: {line_spilt[-1]}')

                is_comment_line = line.startswith("#")
                if is_comment_line:
                    line = line.lstrip('#')

                if re.search('[,，]', line):
                    raw_split_line = [item.strip() for item in re.split('[,，]', line)]
                else:
                    raw_split_line = [line.strip(), '']

                room_record_subtitle = False
                room_burn_subtitle = False
                room_check_interval = None
                room_check_jitter = None
                room_priority = ""
                room_group = ""
                room_owner = ""
                split_line = []
                for split_item in raw_split_line:
                    if not split_item:
                        continue
                    parsed_group = parse_room_group_part(split_item)
                    if parsed_group is not None:
                        room_group = parsed_group
                        continue
                    parsed_owner = parse_room_owner_part(split_item)
                    if parsed_owner is not None:
                        room_owner = parsed_owner
                        continue
                    parsed_flag = parse_room_flag_part(split_item)
                    if parsed_flag:
                        if parsed_flag[0] == "record_subtitle":
                            room_record_subtitle = parsed_flag[1]
                        elif parsed_flag[0] == "burn_subtitle":
                            room_burn_subtitle = parsed_flag[1]
                        continue
                    parsed_option = parse_room_option_part(split_item)
                    if parsed_option:
                        option_key, option_value = parsed_option
                        if option_key == "check_interval":
                            room_check_interval = option_value
                        elif option_key == "check_jitter":
                            room_check_jitter = option_value
                        elif option_key == "priority":
                            room_priority = str(option_value)
                        continue
                    split_line.append(split_item)
                if not split_line:
                    continue

                if len(split_line) == 1:
                    url = split_line[0]
                    quality, name = [video_record_quality, '']
                elif len(split_line) == 2:
                    if contains_url(split_line[0]):
                        quality = video_record_quality
                        url, name = split_line
                    else:
                        quality, url = split_line
                        name = ''
                else:
                    quality, url = split_line[:2]
                    name = '，'.join(split_line[2:])

                if quality not in ("原画", "蓝光", "超清", "高清", "标清", "流畅"):
                    quality = '原画'

                if url not in url_line_list:
                    url_line_list.append(url)
                else:
                    delete_line(url_config_file, origin_line)

                url = 'https://' + url if '://' not in url else url
                room_group = clean_room_group(room_group) or infer_room_group(url)
                url_host = url.split('/')[2]

                platform_host = [
                    'live.douyin.com',
                    'v.douyin.com',
                    'www.douyin.com',
                    'live.kuaishou.com',
                    'www.huya.com',
                    'www.douyu.com',
                    'www.yy.com',
                    'live.bilibili.com',
                    'www.redelight.cn',
                    'www.xiaohongshu.com',
                    'xhslink.com',
                    'www.bigo.tv',
                    'slink.bigovideo.tv',
                    'app.blued.cn',
                    'cc.163.com',
                    'qiandurebo.com',
                    'fm.missevan.com',
                    'look.163.com',
                    'twitcasting.tv',
                    'live.baidu.com',
                    'weibo.com',
                    'fanxing.kugou.com',
                    'fanxing2.kugou.com',
                    'mfanxing.kugou.com',
                    'www.huajiao.com',
                    'www.7u66.com',
                    'wap.7u66.com',
                    'live.acfun.cn',
                    'm.acfun.cn',
                    'live.tlclw.com',
                    'wap.tlclw.com',
                    'live.ybw1666.com',
                    'wap.ybw1666.com',
                    'www.inke.cn',
                    'www.zhihu.com',
                    'www.haixiutv.com',
                    "h5webcdnp.vvxqiu.com",
                    "17.live",
                    'www.lang.live',
                    "m.pp.weimipopo.com",
                    "v.6.cn",
                    "m.6.cn",
                    'www.lehaitv.com',
                    'h.catshow168.com',
                    'e.tb.cn',
                    'huodong.m.taobao.com',
                    '3.cn',
                    'eco.m.jd.com',
                    'www.miguvideo.com',
                    'm.miguvideo.com',
                    'show.lailianjie.com',
                    'www.imkktv.com',
                    'www.picarto.tv'
                ]
                overseas_platform_host = [
                    'www.tiktok.com',
                    'play.sooplive.co.kr',
                    'm.sooplive.co.kr',
                    'www.sooplive.com',
                    'm.sooplive.com',
                    'www.pandalive.co.kr',
                    'www.winktv.co.kr',
                    'www.flextv.co.kr',
                    'www.ttinglive.com',
                    'www.popkontv.com',
                    'www.twitch.tv',
                    'www.liveme.com',
                    'www.showroom-live.com',
                    'chzzk.naver.com',
                    'm.chzzk.naver.com',
                    'live.shopee.',
                    '.shp.ee',
                    'www.youtube.com',
                    'youtu.be',
                    'www.faceit.com',
                    'xhamsterlive.com'
                ]

                platform_host.extend(overseas_platform_host)
                clean_url_host_list = (
                    "live.douyin.com",
                    "live.bilibili.com",
                    "www.huajiao.com",
                    "www.zhihu.com",
                    "www.huya.com",
                    "chzzk.naver.com",
                    "www.liveme.com",
                    "www.haixiutv.com",
                    "v.6.cn",
                    "m.6.cn",
                    'www.lehaitv.com'
                )

                if 'live.shopee.' in url_host or '.shp.ee' in url_host:
                    url_host = 'live.shopee.' if 'live.shopee.' in url_host else '.shp.ee'
                if 'xhamsterlive.com' in url_host:
                    url_host = 'xhamsterlive.com'

                if url_host in platform_host or any(ext in url for ext in (".flv", ".m3u8")):
                    if url_host in clean_url_host_list:
                        url = update_file(url_config_file, old_str=url, new_str=url.split('?')[0])

                    if 'xiaohongshu' in url:
                        host_id = re.search('&host_id=(.*?)(?=&|$)', url)
                        if host_id:
                            new_url = url.split('?')[0] + f'?host_id={host_id.group(1)}'
                            url = update_file(url_config_file, old_str=url, new_str=new_url)

                    with webui_status_lock:
                        url_comments = [i for i in url_comments if url not in i]
                        if is_comment_line:
                            url_comments.append(url)
                    update_room_runtime_options(url, room_check_interval, room_check_jitter, room_priority)
                    if room_owner and not user_has_record_permission(user_config_file, room_owner, url):
                        site_id = detect_permission_site(url)
                        with webui_status_lock:
                            if url not in url_comments:
                                url_comments.append(url)
                        update_webui_room_status(
                            url,
                            status="disabled",
                            configured_name=name,
                            configured_group=room_group,
                            group=room_group,
                            owner=room_owner,
                            quality=quality,
                            message=f"{room_owner}无权录制{permission_site_name(site_id)}",
                            next_check_at="",
                        )
                        continue
                    update_webui_room_status(
                        url,
                        configured_name=name,
                        configured_group=room_group,
                        group=room_group,
                        owner=room_owner,
                        quality=quality,
                    )
                    if not is_comment_line:
                        new_line = (
                            quality,
                            url,
                            name,
                            room_record_subtitle,
                            room_burn_subtitle,
                            room_check_interval,
                            room_check_jitter,
                            room_priority,
                            room_group,
                            room_owner,
                        )
                        url_tuples_list.append(new_line)
                else:
                    if not origin_line.startswith('#'):
                        color_obj.print_colored(f"\r{origin_line.strip()} 本行包含未知链接.此条跳过", color_obj.YELLOW)
                        update_file(url_config_file, old_str=origin_line, new_str=origin_line, start_str='#')

        while len(need_update_line_list):
            a = need_update_line_list.pop()
            replace_words = a.split('|')
            if replace_words[0] != replace_words[1]:
                if replace_words[1].startswith("#"):
                    start_with = '#'
                    new_word = replace_words[1][1:]
                else:
                    start_with = None
                    new_word = replace_words[1]
                update_file(url_config_file, old_str=replace_words[0], new_str=new_word, start_str=start_with)

        text_no_repeat_url = list(set(url_tuples_list))
        active_url_set = {url_tuple[1] for url_tuple in text_no_repeat_url}
        with webui_status_lock:
            running_urls_snapshot = list(running_list)
            disabled_urls_snapshot = set(url_comments)
        removed_running_urls = [
            url for url in running_urls_snapshot
            if url not in active_url_set and url not in disabled_urls_snapshot
        ]
        for removed_url in removed_running_urls:
            with webui_status_lock:
                if removed_url not in url_comments:
                    url_comments.append(removed_url)
            update_webui_room_status(removed_url, status="stopped", message="配置已移除，停止监控")

        with room_dispatch_lock:
            for stale_url in set(room_monitor_configs) - active_url_set:
                room_monitor_configs.pop(stale_url, None)
                room_next_check_monotonic.pop(stale_url, None)
                room_worker_states.pop(stale_url, None)

        ensure_room_dispatcher_started()
        if len(text_no_repeat_url) > 0:
            for url_tuple in text_no_repeat_url:
                if url_tuple[1] in not_record_list:
                    continue

                with webui_status_lock:
                    if url_tuple[1] in running_list:
                        with room_dispatch_lock:
                            room_monitor_configs[url_tuple[1]] = url_tuple
                        continue
                    monitoring = len(running_list) + 1
                    running_list.append(url_tuple[1])

                print(f"\r{'新增' if not first_start else '传入'}地址: {url_tuple[1]}")
                with room_dispatch_lock:
                    room_monitor_configs[url_tuple[1]] = url_tuple
                    room_next_check_monotonic.setdefault(
                        url_tuple[1],
                        time.monotonic() + max(0, local_delay_default * (monitoring - 1)),
                    )
        url_tuples_list = []
        first_start = False

    except Exception as err:
        logger.error(f"错误信息: {err} 发生错误的行数: {err.__traceback__.tb_lineno}")

    if first_run:
        ensure_room_dispatcher_started()
        if show_status_panel:
            t = threading.Thread(target=display_info, args=(), daemon=True)
            t.start()
        t2 = threading.Thread(target=adjust_max_request, args=(), daemon=True)
        t2.start()
        first_run = False

    time.sleep(config_sleep_seconds())
