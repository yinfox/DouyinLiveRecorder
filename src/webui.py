# -*- coding: utf-8 -*-
from __future__ import annotations

import configparser
import datetime
import hmac
import json
import os
import re
import secrets
import socket
import sys
import threading
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from .room import _extract_reflow_params


QUALITIES = ("原画", "蓝光", "超清", "高清", "标清", "流畅")
SENSITIVE_WORDS = ("cookie", "token", "密码", "授权码", "令牌", "secret", "password")
HTTP_URL_PATTERN = re.compile(r"https?://[^\s，,。；;）)】》>\"']+")
DOUYIN_SHORT_URL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
}
DOUYIN_REFLOW_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 "
        "(KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36"
    ),
    "Cookie": "s_v_web_id=verify_lk07kv74_QZYCUApD_xhiB_405x_Ax51_GYO9bUIyZQVf",
}
DOUYIN_WEB_RID_PATTERNS = (
    r'"web_rid"\s*:\s*"([^"]+)"',
    r'"webRid"\s*:\s*"([^"]+)"',
    r'\\"web_rid\\"\s*:\s*\\"([^"\\]+)\\"',
    r'\\"webRid\\"\s*:\s*\\"([^"\\]+)\\"',
)


class ResilientThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128
    request_timeout = 15

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(self.request_timeout)
        return request, client_address

    def handle_error(self, request, client_address) -> None:
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, TimeoutError, socket.timeout)):
            return
        super().handle_error(request, client_address)
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
ROOM_GROUP_LABELS = {"分组", "组", "分类", "平台"}
ROOM_OWNER_LABELS = {"用户", "用户码", "账号", "所有者"}
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
PLATFORM_GROUP_RULES = (
    ("douyin.com", "抖音"),
    ("kuaishou.com", "快手"),
    ("youtube.com", "YouTube"),
    ("youtu.be", "YouTube"),
    ("tiktok.com", "TikTok"),
    ("bilibili.com", "B站"),
    ("huya.com", "虎牙"),
    ("douyu.com", "斗鱼"),
    ("yy.com", "YY"),
    ("xiaohongshu.com", "小红书"),
    ("xhslink.com", "小红书"),
    ("bigo.tv", "Bigo"),
    ("bigovideo.tv", "Bigo"),
    ("blued.cn", "Blued"),
    ("sooplive.", "SOOP"),
    ("pandalive.co.kr", "PandaTV"),
    ("winktv.co.kr", "WinkTV"),
    ("flextv.co.kr", "FlexTV"),
    ("ttinglive.com", "FlexTV"),
    ("popkontv.com", "PopkonTV"),
    ("twitch.tv", "Twitch"),
    ("liveme.com", "LiveMe"),
    ("showroom-live.com", "ShowRoom"),
    ("chzzk.naver.com", "CHZZK"),
    ("shopee.", "Shopee"),
    ("shp.ee", "Shopee"),
    ("faceit.com", "Faceit"),
    ("picarto.tv", "Picarto"),
    ("xhamsterlive.com", "xHamsterLive"),
    ("acfun.cn", "Acfun"),
    ("zhihu.com", "知乎"),
    ("huajiao.com", "花椒"),
    ("missevan.com", "猫耳FM"),
    ("miguvideo.com", "咪咕"),
    ("tb.cn", "淘宝"),
    ("taobao.com", "淘宝"),
    ("jd.com", "京东"),
    ("3.cn", "京东"),
)
PERMISSION_SITE_RULES = (
    ("douyin", "抖音", ("douyin.com",)),
    ("kuaishou", "快手", ("kuaishou.com",)),
    ("youtube", "YouTube", ("youtube.com", "youtu.be")),
    ("xhamsterlive", "xHamsterLive", ("xhamsterlive.com",)),
    ("tiktok", "TikTok", ("tiktok.com",)),
    ("bilibili", "B站", ("bilibili.com",)),
    ("huya", "虎牙", ("huya.com",)),
    ("douyu", "斗鱼", ("douyu.com",)),
    ("yy", "YY", ("yy.com",)),
    ("xiaohongshu", "小红书", ("xiaohongshu.com", "xhslink.com")),
    ("bigo", "Bigo", ("bigo.tv", "bigovideo.tv")),
    ("blued", "Blued", ("blued.cn",)),
    ("soop", "SOOP", ("sooplive.",)),
    ("pandatv", "PandaTV", ("pandalive.co.kr",)),
    ("winktv", "WinkTV", ("winktv.co.kr",)),
    ("flextv", "FlexTV", ("flextv.co.kr", "ttinglive.com")),
    ("popkontv", "PopkonTV", ("popkontv.com",)),
    ("twitch", "Twitch", ("twitch.tv",)),
    ("liveme", "LiveMe", ("liveme.com",)),
    ("showroom", "ShowRoom", ("showroom-live.com",)),
    ("chzzk", "CHZZK", ("chzzk.naver.com",)),
    ("shopee", "Shopee", ("shopee.", "shp.ee")),
    ("faceit", "Faceit", ("faceit.com",)),
    ("picarto", "Picarto", ("picarto.tv",)),
    ("taobao", "淘宝", ("tb.cn", "taobao.com")),
    ("jd", "京东", ("jd.com", "3.cn")),
    ("migu", "咪咕", ("miguvideo.com",)),
    ("acfun", "Acfun", ("acfun.cn",)),
    ("zhihu", "知乎", ("zhihu.com",)),
    ("huajiao", "花椒", ("huajiao.com",)),
    ("weibo", "微博", ("weibo.com",)),
    ("baidu", "百度", ("baidu.com",)),
    ("kugou", "酷狗", ("kugou.com",)),
    ("custom", "自定义直链", (".m3u8", ".flv")),
)
PERMISSION_SITE_OPTIONS = [
    {"id": site_id, "name": name}
    for site_id, name, _patterns in PERMISSION_SITE_RULES
]
PERMISSION_SITE_NAMES = {site["id"]: site["name"] for site in PERMISSION_SITE_OPTIONS}


def contains_url(text: str) -> bool:
    pattern = r"(https?://)?(www\.)?[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+(:\d+)?(/.*)?"
    return re.search(pattern, text) is not None


def extract_http_url(text: str) -> str:
    match = HTTP_URL_PATTERN.search(text)
    if not match:
        return ""
    return match.group(0).rstrip(".。!！?？;；:：")


def extract_anchor_name(text: str) -> str:
    patterns = (
        r"【([^】]{1,80})】\s*正在直播",
        r"@([^，,。；;\s]{1,80})\s*正在直播",
        r"主播[:：]\s*([^，,。；;\s]{1,80})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return strip_anchor_prefix(match.group(1)).strip()
    return ""


def normalize_url(url: str) -> str:
    url = url.strip()
    if url and "://" not in url:
        url = "https://" + url
    return url


def clean_room_group(group: Any) -> str:
    return re.sub(r"[,，\r\n]+", " ", str(group or "")).strip()


def infer_room_group(url: str) -> str:
    normalized_url = normalize_url(str(url or "")).lower()
    for needle, group in PLATFORM_GROUP_RULES:
        if needle in normalized_url:
            return group
    if any(ext in normalized_url for ext in (".flv", ".m3u8")):
        return "自定义"
    return "其他" if normalized_url else ""


def is_douyin_short_url(url: str) -> bool:
    try:
        return urlparse(url).netloc.lower() == "v.douyin.com"
    except ValueError:
        return False


def extract_douyin_live_url(text: str) -> str:
    match = re.search(r"https://live\.douyin\.com/([^\"'\\<\s?]+)", text)
    if match:
        return f"https://live.douyin.com/{match.group(1)}"

    for pattern in DOUYIN_WEB_RID_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return f"https://live.douyin.com/{match.group(1)}"
    return ""


def nested_value(value: Any, key: str) -> str:
    if isinstance(value, dict):
        if key in value:
            return str(value[key])
        for item in value.values():
            found = nested_value(item, key)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = nested_value(item, key)
            if found:
                return found
    return ""


def resolve_douyin_redirect(url: str) -> tuple[str, str]:
    request = Request(url, headers=DOUYIN_SHORT_URL_HEADERS)
    with urlopen(request, timeout=15) as response:
        text = response.read().decode("utf-8", errors="ignore")
        return str(response.geturl()), text


def resolve_douyin_reflow_live_url(url: str) -> str:
    parsed_url = urlparse(url)
    if parsed_url.netloc.lower() == "live.douyin.com":
        return normalize_url(url.split("?", 1)[0])

    try:
        request = Request(url, headers=DOUYIN_SHORT_URL_HEADERS)
        with urlopen(request, timeout=15) as response:
            live_url = extract_douyin_live_url(response.read().decode("utf-8", errors="ignore"))
            if live_url:
                return live_url
    except Exception:
        pass

    room_id, sec_user_id = _extract_reflow_params(url)
    if not room_id or not sec_user_id:
        return ""

    params = {
        "verifyFp": "verify_lk07kv74_QZYCUApD_xhiB_405x_Ax51_GYO9bUIyZQVf",
        "type_id": "0",
        "live_id": "1",
        "room_id": room_id,
        "sec_user_id": sec_user_id,
        "app_id": "1128",
    }
    api = f"https://webcast.amemv.com/webcast/room/reflow/info/?{urlencode(params)}"
    request = Request(api, headers=DOUYIN_REFLOW_HEADERS)
    with urlopen(request, timeout=15) as response:
        response_text = response.read().decode("utf-8", errors="ignore")
        live_url = extract_douyin_live_url(response_text)
        if live_url:
            return live_url
        json_data = json.loads(response_text)

    web_rid = nested_value(json_data, "web_rid") or nested_value(json_data, "webRid")
    return f"https://live.douyin.com/{web_rid}" if web_rid else ""


def resolve_douyin_short_url(url: str) -> str:
    normalized_url = normalize_url(url)
    if not is_douyin_short_url(normalized_url):
        return normalized_url

    try:
        redirect_url, page_text = resolve_douyin_redirect(normalized_url)
        live_url = extract_douyin_live_url(page_text)
        if live_url:
            return live_url
        live_url = resolve_douyin_reflow_live_url(redirect_url)
        if live_url:
            return live_url
    except Exception:
        pass
    return normalized_url


def strip_anchor_prefix(name: str) -> str:
    name = name.strip()
    if "主播:" in name:
        name = name.split("主播:", 1)[1].strip()
    return name


def parse_yes_no(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if text in YES_VALUES:
        return True
    if text in NO_VALUES:
        return False
    return None


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

    match = re.match(r"^([^:：]{1,12})\s*[:：]\s*(.+)$", text)
    if not match:
        return None
    key = ROOM_OPTION_LABELS.get(match.group(1).strip())
    if not key:
        return None

    raw_value = match.group(2).strip()
    if key == "priority":
        priority = ROOM_STAR_PRIORITY_ALIASES.get(raw_value)
        return (key, priority) if priority else None

    try:
        value = int(float(raw_value))
    except ValueError:
        return None
    if key == "check_interval":
        return key, max(1, value)
    if key == "check_jitter":
        return key, max(0, value)
    return None


def parse_room_group_part(part: str) -> str | None:
    match = re.match(r"^([^:：]{1,12})\s*[:：]\s*(.+)$", str(part or "").strip())
    if not match:
        return None
    if match.group(1).strip() not in ROOM_GROUP_LABELS:
        return None
    group = clean_room_group(match.group(2))
    return group if group else None


def parse_room_owner_part(part: str) -> str | None:
    match = re.match(r"^([^:：]{1,12})\s*[:：]\s*(.+)$", str(part or "").strip())
    if not match:
        return None
    if match.group(1).strip() not in ROOM_OWNER_LABELS:
        return None
    owner = re.sub(r"[^\w.@+-]", "_", match.group(2).strip())
    return owner.strip("_") or None


def detect_permission_site(url: str) -> str:
    lower_url = str(url or "").lower()
    for site_id, _name, patterns in PERMISSION_SITE_RULES:
        if any(pattern in lower_url for pattern in patterns):
            return site_id
    return "unknown"


def permission_site_name(site_id: str) -> str:
    return PERMISSION_SITE_NAMES.get(site_id, site_id or "未知网站")


def parse_room_line(raw_line: str, index: int, default_quality: str = "原画") -> dict[str, Any] | None:
    raw = raw_line.rstrip("\r\n")
    stripped = raw.strip()
    if not stripped:
        return None

    enabled = not stripped.startswith("#")
    payload = stripped.lstrip("#").strip() if not enabled else stripped
    if not payload:
        return None
    shared_url = extract_http_url(payload)
    shared_name = extract_anchor_name(payload)

    raw_parts = [part.strip() for part in re.split(r"[,，]", payload)]
    room_flags = {"record_subtitle": False, "burn_subtitle": False}
    room_options = {"priority": "", "check_interval": None, "check_jitter": None}
    group = ""
    owner = ""
    name_parts: list[str] = []
    parts: list[str] = []
    for part in raw_parts:
        if not part:
            continue
        parsed_group = parse_room_group_part(part)
        if parsed_group is not None:
            group = parsed_group
            continue
        parsed_owner = parse_room_owner_part(part)
        if parsed_owner is not None:
            owner = parsed_owner
            continue
        parsed_flag = parse_room_flag_part(part)
        if parsed_flag:
            room_flags[parsed_flag[0]] = parsed_flag[1]
            continue
        parsed_option = parse_room_option_part(part)
        if parsed_option:
            room_options[parsed_option[0]] = parsed_option[1]
            continue
        if part.startswith(("主播:", "主播：")):
            anchor_part = strip_anchor_prefix(part)
            embedded_url = extract_http_url(anchor_part)
            if embedded_url:
                parts.append(embedded_url)
                anchor_part = anchor_part.replace(embedded_url, "").strip()
            if anchor_part:
                name_parts.append(anchor_part)
            continue
        parts.append(part)
    if not parts:
        return None
    quality = default_quality if default_quality in QUALITIES else "原画"
    url = ""
    name = ""

    if len(parts) == 1:
        url = shared_url or parts[0]
        name = shared_name
    elif len(parts) == 2:
        if contains_url(parts[0]):
            url = extract_http_url(parts[0]) or parts[0]
            name = parts[1]
        else:
            quality = parts[0]
            url = extract_http_url(parts[1]) or parts[1]
            name = shared_name
    else:
        quality = parts[0]
        url = shared_url or extract_http_url(parts[1]) or parts[1]
        name = shared_name or "，".join(parts[2:])

    if quality not in QUALITIES:
        quality = default_quality if default_quality in QUALITIES else "原画"

    url = normalize_url(url)
    group = clean_room_group(group) or infer_room_group(url)
    if name_parts:
        name = "，".join(part for part in name_parts if part)
    name = strip_anchor_prefix(name)
    valid = bool(url and contains_url(url))

    return {
        "id": index,
        "enabled": enabled,
        "quality": quality,
        "url": url,
        "name": name,
        "group": group,
        "owner": owner,
        "record_subtitle": room_flags["record_subtitle"],
        "burn_subtitle": room_flags["burn_subtitle"],
        "priority": room_options["priority"],
        "check_interval": room_options["check_interval"],
        "check_jitter": room_options["check_jitter"],
        "raw": raw,
        "valid": valid,
    }


def normalize_room_payload(room: dict[str, Any], default_quality: str = "原画") -> dict[str, Any]:
    raw_url = str(room.get("url") or "")
    parsed = parse_room_line(raw_url, 0, default_quality)
    normalized = dict(room)
    if parsed and parsed.get("valid"):
        normalized["url"] = resolve_douyin_short_url(parsed["url"])
        if is_douyin_short_url(parsed["url"]) and normalized["url"] == parsed["url"]:
            raise ValueError("抖音短链转换失败，请粘贴浏览器跳转后的 live.douyin.com 地址")
        if not str(normalized.get("name") or "").strip() and parsed.get("name"):
            normalized["name"] = parsed["name"]
        if not str(normalized.get("quality") or "").strip():
            normalized["quality"] = parsed["quality"]
        if not str(normalized.get("group") or "").strip() and parsed.get("group"):
            normalized["group"] = parsed["group"]
        if not str(normalized.get("owner") or "").strip() and parsed.get("owner"):
            normalized["owner"] = parsed["owner"]
        for key in ("record_subtitle", "burn_subtitle"):
            if not bool(normalized.get(key, False)) and parsed.get(key):
                normalized[key] = True
        for key in ("priority", "check_interval", "check_jitter"):
            if not normalized.get(key) and parsed.get(key) is not None:
                normalized[key] = parsed[key]
    normalized["group"] = clean_room_group(normalized.get("group")) or infer_room_group(normalized.get("url", ""))
    normalized["owner"] = parse_room_owner_part(f"用户: {normalized.get('owner') or ''}") or ""
    return normalized


def format_room_line(room: dict[str, Any], default_quality: str = "原画") -> str:
    quality = str(room.get("quality") or default_quality or "原画").strip()
    if quality not in QUALITIES:
        quality = default_quality if default_quality in QUALITIES else "原画"

    url = normalize_url(str(room.get("url") or ""))
    name = strip_anchor_prefix(str(room.get("name") or ""))
    group = clean_room_group(room.get("group")) or infer_room_group(url)
    owner = parse_room_owner_part(f"用户: {room.get('owner') or ''}") or ""
    payload = f"{quality},{url}"
    if name:
        payload = f"{payload},主播: {name}"
    if group:
        payload = f"{payload},分组: {group}"
    if owner:
        payload = f"{payload},用户: {owner}"
    if bool(room.get("record_subtitle", False)):
        payload = f"{payload},字幕: 是"
    if bool(room.get("burn_subtitle", False)):
        payload = f"{payload},烧录: 是"
    priority = ROOM_STAR_PRIORITY_ALIASES.get(str(room.get("priority") or "").strip())
    if priority:
        payload = f"{payload},{priority}"
    if room.get("check_interval") not in (None, ""):
        payload = f"{payload},巡检:{max(1, int(float(room.get('check_interval'))))}"
    if room.get("check_jitter") not in (None, ""):
        payload = f"{payload},浮动:{max(0, int(float(room.get('check_jitter'))))}"
    if not bool(room.get("enabled", True)):
        payload = "#" + payload
    return payload


def read_text_lines(path: str | Path, encoding: str) -> list[str]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding=encoding, errors="ignore") as file:
        return file.readlines()


def write_text_lines(path: str | Path, lines: list[str], encoding: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding) as file:
        file.write("".join(lines))


def read_rooms(path: str | Path, encoding: str, default_quality: str = "原画") -> list[dict[str, Any]]:
    rooms: list[dict[str, Any]] = []
    for index, raw_line in enumerate(read_text_lines(path, encoding)):
        room = parse_room_line(raw_line, index, default_quality)
        if room:
            rooms.append(room)
    return rooms


def append_room(
        path: str | Path,
        encoding: str,
        room: dict[str, Any],
        default_quality: str,
        lock: threading.RLock | threading.Lock,
) -> dict[str, Any]:
    room = normalize_room_payload(room, default_quality)
    line = format_room_line(room, default_quality)
    parsed = parse_room_line(line, 0, default_quality)
    if not parsed or not parsed.get("valid"):
        raise ValueError("直播间 URL 无效")

    with lock:
        lines = read_text_lines(path, encoding)
        for index, raw_line in enumerate(lines):
            existing = parse_room_line(raw_line, index, default_quality)
            if not existing or existing.get("url") != parsed["url"]:
                continue
            updated = dict(existing)
            updated["enabled"] = parsed["enabled"]
            updated["quality"] = parsed["quality"]
            updated["url"] = parsed["url"]
            updated["group"] = parsed.get("group") or infer_room_group(parsed["url"])
            updated["owner"] = parsed.get("owner") or updated.get("owner") or ""
            updated["record_subtitle"] = parsed["record_subtitle"]
            updated["burn_subtitle"] = parsed["burn_subtitle"]
            if parsed.get("name"):
                updated["name"] = parsed["name"]
            updated_line = format_room_line(updated, default_quality)
            lines[index] = updated_line + "\n"
            write_text_lines(path, lines, encoding)
            result = parse_room_line(lines[index], index, default_quality) or {}
            result["existing"] = True
            return result
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.append(line + "\n")
        write_text_lines(path, lines, encoding)
        parsed["id"] = len(lines) - 1
        parsed["existing"] = False
        return parsed or {}


def append_rooms(
        path: str | Path,
        encoding: str,
        text: str,
        default_quality: str,
        lock: threading.RLock | threading.Lock,
        owner: str = "",
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    pending_urls: set[str] = set()
    for raw_line in iter_room_candidates(text):
        parsed = parse_room_line(raw_line, 0, default_quality)
        if not parsed or not parsed.get("valid"):
            continue
        try:
            parsed = normalize_room_payload(parsed, default_quality)
        except ValueError:
            continue
        if owner:
            parsed["owner"] = owner
        line = format_room_line(parsed, default_quality)
        parsed = parse_room_line(line, 0, default_quality)
        if not parsed or not parsed.get("valid") or parsed["url"] in pending_urls:
            continue
        pending_urls.add(parsed["url"])
        parsed["raw"] = line
        prepared.append(parsed)

    added: list[dict[str, Any]] = []
    with lock:
        lines = read_text_lines(path, encoding)
        existing_urls = {
            room["url"]
            for room in (
                parse_room_line(raw_line, index, default_quality)
                for index, raw_line in enumerate(lines)
            )
            if room and room.get("url")
        }
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"

        for parsed in prepared:
            if parsed["url"] in existing_urls:
                for index, raw_line in enumerate(lines):
                    existing = parse_room_line(raw_line, index, default_quality)
                    if not existing or existing.get("url") != parsed["url"]:
                        continue
                    updated = dict(existing)
                    updated["enabled"] = parsed["enabled"]
                    updated["quality"] = parsed["quality"]
                    updated["url"] = parsed["url"]
                    updated["group"] = parsed.get("group") or infer_room_group(parsed["url"])
                    updated["owner"] = parsed.get("owner") or updated.get("owner") or ""
                    updated["record_subtitle"] = parsed["record_subtitle"]
                    updated["burn_subtitle"] = parsed["burn_subtitle"]
                    if parsed.get("name"):
                        updated["name"] = parsed["name"]
                    updated_line = format_room_line(updated, default_quality)
                    lines[index] = updated_line + "\n"
                    result = parse_room_line(lines[index], index, default_quality) or {}
                    result["existing"] = True
                    result["raw"] = updated_line
                    added.append(result)
                    break
                continue
            line = str(parsed.get("raw") or format_room_line(parsed, default_quality))
            lines.append(line + "\n")
            existing_urls.add(parsed["url"])
            parsed["id"] = len(lines) - 1
            parsed["raw"] = line
            parsed["existing"] = False
            added.append(parsed)

        write_text_lines(path, lines, encoding)
    return added


def iter_room_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    buffer: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        buffer.append(line)
        if extract_http_url(line):
            candidates.append(" ".join(buffer))
            buffer = []
    if not candidates and text.strip():
        candidates.append(text.strip())
    return candidates


def update_room(
        path: str | Path,
        encoding: str,
        room_id: int,
        changes: dict[str, Any],
        default_quality: str,
        lock: threading.RLock | threading.Lock,
) -> dict[str, Any]:
    with lock:
        lines = read_text_lines(path, encoding)
        if room_id < 0 or room_id >= len(lines):
            raise ValueError("直播间不存在")
        current = parse_room_line(lines[room_id], room_id, default_quality)
        if not current:
            raise ValueError("这一行不是有效直播间")

    current.update({key: value for key, value in changes.items() if value is not None})
    current = normalize_room_payload(current, default_quality)
    line = format_room_line(current, default_quality)
    parsed = parse_room_line(line, room_id, default_quality)
    if not parsed or not parsed.get("valid"):
        raise ValueError("直播间 URL 无效")

    with lock:
        lines = read_text_lines(path, encoding)
        if room_id < 0 or room_id >= len(lines):
            raise ValueError("直播间不存在")
        if not parse_room_line(lines[room_id], room_id, default_quality):
            raise ValueError("这一行不是有效直播间")
        lines[room_id] = line + "\n"
        write_text_lines(path, lines, encoding)
        return parse_room_line(lines[room_id], room_id, default_quality) or {}


def delete_room(
        path: str | Path,
        encoding: str,
        room_id: int,
        lock: threading.RLock | threading.Lock,
) -> None:
    with lock:
        lines = read_text_lines(path, encoding)
        if room_id < 0 or room_id >= len(lines):
            raise ValueError("直播间不存在")
        del lines[room_id]
        write_text_lines(path, lines, encoding)


def patch_rooms(
        path: str | Path,
        encoding: str,
        room_ids: list[int],
        changes: dict[str, Any],
        default_quality: str,
        lock: threading.RLock | threading.Lock,
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    with lock:
        lines = read_text_lines(path, encoding)
        for room_id in sorted(set(room_ids)):
            if room_id < 0 or room_id >= len(lines):
                continue
            current = parse_room_line(lines[room_id], room_id, default_quality)
            if not current:
                continue
            for key, value in changes.items():
                if value is not None and value != "":
                    current[key] = value
            lines[room_id] = format_room_line(current, default_quality) + "\n"
            parsed = parse_room_line(lines[room_id], room_id, default_quality)
            if parsed:
                updated.append(parsed)
        write_text_lines(path, lines, encoding)
    return updated


def disable_room_by_url(
        path: str | Path,
        encoding: str,
        url: str,
        default_quality: str,
        lock: threading.RLock | threading.Lock,
) -> dict[str, Any]:
    target_url = normalize_url(url)
    if not target_url:
        raise ValueError("直播间 URL 不能为空")

    with lock:
        lines = read_text_lines(path, encoding)
        for index, line in enumerate(lines):
            room = parse_room_line(line, index, default_quality)
            if not room or room.get("url") != target_url:
                continue
            room["enabled"] = False
            lines[index] = format_room_line(room, default_quality) + "\n"
            write_text_lines(path, lines, encoding)
            return parse_room_line(lines[index], index, default_quality) or {}

    raise ValueError("没有找到对应直播间")


def read_config_sections(path: str | Path, encoding: str) -> list[dict[str, Any]]:
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.read(path, encoding=encoding)
    sections: list[dict[str, Any]] = []
    for section in parser.sections():
        items = []
        for key, value in parser.items(section):
            items.append({
                "key": key,
                "value": value,
                "sensitive": any(word.lower() in key.lower() for word in SENSITIVE_WORDS),
            })
        if section == "录制设置":
            existing_keys = {item["key"] for item in items}
            for key, value in (
                ("生成字幕文件", "否"),
                ("字幕内容类型(弹幕/时间)", "弹幕"),
                ("是否将字幕烧录进视频", "否"),
            ):
                if key not in existing_keys:
                    items.append({
                        "key": key,
                        "value": value,
                        "sensitive": False,
                    })
        sections.append({"name": section, "items": items})
    return sections


def get_config_value(
        path: str | Path,
        encoding: str,
        section: str,
        key: str,
        fallback: str = "",
) -> str:
    section_norm = section.strip().casefold()
    key_norm = key.strip().casefold()
    section_pattern = re.compile(r"^\s*\[([^\]]+)]\s*$")
    key_pattern = re.compile(r"^\s*([^#;][^=]*?)\s*=\s*(.*)$")
    current_section_matches = False
    for line in read_text_lines(path, encoding):
        section_match = section_pattern.match(line.strip())
        if section_match:
            current_section_matches = section_match.group(1).strip().casefold() == section_norm
            continue
        if not current_section_matches:
            continue
        key_match = key_pattern.match(line)
        if key_match and key_match.group(1).strip().casefold() == key_norm:
            return key_match.group(2).strip()
    return fallback


def set_config_value(
        path: str | Path,
        encoding: str,
        section: str,
        key: str,
        value: str,
        lock: threading.RLock | threading.Lock,
) -> None:
    section = section.strip()
    key = key.strip()
    if not section or not key:
        raise ValueError("配置分组和配置项不能为空")
    if any(char in section or char in key or char in str(value) for char in ("\r", "\n")):
        raise ValueError("配置分组、配置项和值不能包含换行")
    value = str(value)

    with lock:
        lines = read_text_lines(path, encoding)
        section_pattern = re.compile(r"^\s*\[([^\]]+)]\s*$")
        key_pattern = re.compile(r"^\s*([^#;][^=]*?)\s*=")
        target_section_norm = section.casefold()
        target_key_norm = key.casefold()
        current_section_matches = False
        target_start: int | None = None
        insert_at: int | None = None

        for index, line in enumerate(lines):
            section_match = section_pattern.match(line.strip())
            if section_match:
                if current_section_matches and insert_at is None:
                    insert_at = index
                current_section_matches = section_match.group(1).strip().casefold() == target_section_norm
                if current_section_matches:
                    target_start = index
                continue

            if current_section_matches:
                key_match = key_pattern.match(line)
                if key_match and key_match.group(1).strip().casefold() == target_key_norm:
                    existing_key = key_match.group(1).strip()
                    lines[index] = f"{existing_key} = {value}\n"
                    write_text_lines(path, lines, encoding)
                    return

        if target_start is not None:
            insert_at = insert_at if insert_at is not None else len(lines)
            lines.insert(insert_at, f"{key} = {value}\n")
        else:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += "\n"
            if lines and lines[-1].strip():
                lines.append("\n")
            lines.extend([f"[{section}]\n", f"{key} = {value}\n"])
        write_text_lines(path, lines, encoding)


def normalize_allowed_sites(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_sites = re.split(r"[,，\s]+", value)
    elif isinstance(value, list):
        raw_sites = value
    else:
        raw_sites = []
    valid_ids = {site["id"] for site in PERMISSION_SITE_OPTIONS}
    allowed = []
    for site in raw_sites:
        site_id = str(site or "").strip()
        if not site_id:
            continue
        if site_id == "*" or site_id in valid_ids:
            if site_id not in allowed:
                allowed.append(site_id)
    return allowed


def load_user_store(path: str | Path) -> dict[str, Any]:
    user_path = Path(path)
    if not user_path.exists():
        return {"version": 1, "users": []}
    try:
        data = json.loads(user_path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "users": []}
    if not isinstance(data, dict):
        return {"version": 1, "users": []}
    users = data.get("users")
    if not isinstance(users, list):
        users = []
    data["version"] = 1
    data["users"] = [normalize_user_record(user) for user in users if isinstance(user, dict)]
    return data


def save_user_store(path: str | Path, data: dict[str, Any]) -> None:
    user_path = Path(path)
    user_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.write_text(
        json.dumps({"version": 1, "users": data.get("users", [])}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_user_record(user: dict[str, Any]) -> dict[str, Any]:
    username = re.sub(r"[^\w.@+-]", "_", str(user.get("username") or "").strip()).strip("_")
    return {
        "username": username,
        "password": str(user.get("password") or ""),
        "code": str(user.get("code") or secrets.token_urlsafe(8)),
        "enabled": bool(user.get("enabled", True)),
        "allowed_sites": normalize_allowed_sites(user.get("allowed_sites")),
        "remark": str(user.get("remark") or ""),
    }


def public_user_record(user: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_user_record(user)
    normalized.pop("password", None)
    return normalized


def user_identity(
        username: str,
        role: str,
        allowed_sites: list[str] | None = None,
        code: str = "",
) -> dict[str, Any]:
    return {
        "username": username,
        "code": code,
        "role": role,
        "allowed_sites": ["*"] if role == "admin" else normalize_allowed_sites(allowed_sites or []),
    }


def find_managed_user(path: str | Path, username: str) -> dict[str, Any] | None:
    username = str(username or "").strip()
    for user in load_user_store(path).get("users", []):
        if user.get("username") == username or user.get("code") == username:
            return user
    return None


def user_has_record_permission(path: str | Path, username: str, url: str) -> bool:
    if not username:
        return True
    user = find_managed_user(path, username)
    if not user or not user.get("enabled", True):
        return False
    return identity_has_record_permission(
        user_identity(user.get("username", username), "user", user.get("allowed_sites"), user.get("code", "")),
        url,
    )


def identity_has_record_permission(identity: dict[str, Any] | None, url: str) -> bool:
    if not identity or identity.get("role") == "admin":
        return True
    allowed_sites = normalize_allowed_sites(identity.get("allowed_sites"))
    site_id = detect_permission_site(url)
    return "*" in allowed_sites or site_id in allowed_sites


def permission_denied_message(identity: dict[str, Any] | None, url: str) -> str:
    site_id = detect_permission_site(url)
    username = (identity or {}).get("username") or "该用户"
    return f"{username}无权录制{permission_site_name(site_id)}"


def build_static_html() -> str:
    return WEBUI_HTML


class WebUISessionStore:
    def __init__(self, session_hours: int = 24) -> None:
        self.session_seconds = max(1, session_hours) * 3600
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def create(self, identity: dict[str, Any]) -> str:
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.datetime.now() + datetime.timedelta(seconds=self.session_seconds)
        with self._lock:
            self._sessions[session_id] = {
                "expires_at": expires_at,
                "identity": identity,
            }
            self._cleanup_locked()
        return session_id

    def valid(self, session_id: str) -> bool:
        return bool(self.get(session_id))

    def get(self, session_id: str) -> dict[str, Any] | None:
        if not session_id:
            return None
        now = datetime.datetime.now()
        with self._lock:
            session = self._sessions.get(session_id)
            expires_at = session.get("expires_at") if isinstance(session, dict) else None
            if not expires_at or expires_at <= now:
                self._sessions.pop(session_id, None)
                return None
            return dict(session.get("identity") or {})

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def replace_identity(self, session_id: str, identity: dict[str, Any]) -> None:
        if not session_id:
            return
        with self._lock:
            session = self._sessions.get(session_id)
            if isinstance(session, dict):
                session["identity"] = identity

    def replace_admin_sessions(self, session_id: str, identity: dict[str, Any]) -> None:
        with self._lock:
            for current_id, session in list(self._sessions.items()):
                current_identity = session.get("identity") if isinstance(session, dict) else {}
                if not isinstance(current_identity, dict) or current_identity.get("role") != "admin":
                    continue
                if current_id == session_id:
                    session["identity"] = identity
                else:
                    self._sessions.pop(current_id, None)

    def _cleanup_locked(self) -> None:
        now = datetime.datetime.now()
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if not isinstance(session, dict) or session.get("expires_at") <= now
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)


class RecorderWebUI:
    def __init__(
            self,
            *,
            config_file: str,
            url_config_file: str,
            user_config_file: str,
            encoding: str,
            file_lock: threading.RLock | threading.Lock,
            status_provider: Callable[[], dict[str, Any]],
            default_quality_provider: Callable[[], str],
            history_provider: Callable[[list[dict[str, Any]], set[str] | None], dict[str, Any]] | None = None,
            runtime_stop_callback: Callable[[list[str]], None] | None = None,
            username: str = "admin",
            password: str = "admin",
            session_hours: int = 24,
    ) -> None:
        self.config_file = config_file
        self.url_config_file = url_config_file
        self.user_config_file = user_config_file
        self.encoding = encoding
        self.file_lock = file_lock
        self.status_provider = status_provider
        self.default_quality_provider = default_quality_provider
        self.history_provider = history_provider
        self.runtime_stop_callback = runtime_stop_callback
        self.username = username.strip() or "admin"
        self.password = password
        self.sessions = WebUISessionStore(session_hours)

    def admin_credentials(self) -> tuple[str, str]:
        expected_username = get_config_value(
            self.config_file, self.encoding, "WebUI", "WebUI登录用户名", self.username
        ).strip() or self.username
        expected_password = get_config_value(
            self.config_file, self.encoding, "WebUI", "WebUI登录密码", self.password
        )
        username_override = os.getenv("WEBUI_USERNAME")
        password_override = os.getenv("WEBUI_PASSWORD")
        if username_override and username_override.strip():
            expected_username = username_override.strip()
        if password_override:
            expected_password = password_override
        return expected_username, expected_password

    @staticmethod
    def env_credential_overrides() -> tuple[bool, bool]:
        username_override = os.getenv("WEBUI_USERNAME")
        password_override = os.getenv("WEBUI_PASSWORD")
        return bool(username_override and username_override.strip()), bool(password_override)

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        expected_username, expected_password = self.admin_credentials()
        if (
            hmac.compare_digest(username, expected_username)
            and hmac.compare_digest(password, expected_password)
        ):
            return user_identity(expected_username, "admin")

        for user in load_user_store(self.user_config_file).get("users", []):
            if not user.get("enabled", True):
                continue
            if (
                hmac.compare_digest(username, str(user.get("username") or ""))
                and hmac.compare_digest(password, str(user.get("password") or ""))
            ):
                return user_identity(user["username"], "user", user.get("allowed_sites"), user.get("code", ""))
        return None

    def check_login(self, username: str, password: str) -> bool:
        return bool(self.authenticate(username, password))

    @staticmethod
    def is_admin(identity: dict[str, Any] | None) -> bool:
        return bool(identity and identity.get("role") == "admin")

    @staticmethod
    def identity_username(identity: dict[str, Any] | None) -> str:
        return str((identity or {}).get("username") or "")

    @staticmethod
    def identity_identifiers(identity: dict[str, Any] | None) -> set[str]:
        return {
            str(value)
            for value in ((identity or {}).get("username"), (identity or {}).get("code"))
            if value
        }

    def assert_admin(self, identity: dict[str, Any] | None) -> None:
        if not self.is_admin(identity):
            raise PermissionError("需要管理员权限")

    def assert_room_access(self, identity: dict[str, Any] | None, room: dict[str, Any]) -> None:
        if self.is_admin(identity):
            return
        if room.get("owner") not in self.identity_identifiers(identity):
            raise PermissionError("无权操作这个直播间")

    def assert_record_permission(self, identity: dict[str, Any] | None, url: str) -> None:
        if not identity_has_record_permission(identity, url):
            raise PermissionError(permission_denied_message(identity, url))

    def user_payload(self, identity: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "username": self.identity_username(identity),
            "code": (identity or {}).get("code", ""),
            "role": (identity or {}).get("role", ""),
            "allowed_sites": normalize_allowed_sites((identity or {}).get("allowed_sites")),
            "site_options": PERMISSION_SITE_OPTIONS,
        }

    def managed_users(self, identity: dict[str, Any] | None) -> list[dict[str, Any]]:
        self.assert_admin(identity)
        return [public_user_record(user) for user in load_user_store(self.user_config_file).get("users", [])]

    def admin_account(self, identity: dict[str, Any] | None) -> dict[str, Any]:
        self.assert_admin(identity)
        username_override, password_override = self.env_credential_overrides()
        username, _password = self.admin_credentials()
        return {
            "username": username,
            "username_overridden": username_override,
            "password_overridden": password_override,
        }

    def update_admin_account(self, identity: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any]:
        self.assert_admin(identity)
        username_override, password_override = self.env_credential_overrides()
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")

        if not username:
            raise ValueError("管理员用户名不能为空")
        if username_override:
            current_username, _password = self.admin_credentials()
            if username != current_username:
                raise PermissionError("管理员用户名已被 WEBUI_USERNAME 环境变量覆盖")
        else:
            set_config_value(
                self.config_file,
                self.encoding,
                "WebUI",
                "WebUI登录用户名",
                username,
                self.file_lock,
            )

        if password:
            if password_override:
                raise PermissionError("管理员密码已被 WEBUI_PASSWORD 环境变量覆盖")
            set_config_value(
                self.config_file,
                self.encoding,
                "WebUI",
                "WebUI登录密码",
                password,
                self.file_lock,
            )
        return self.admin_account(identity)

    def export_rooms(self, identity: dict[str, Any] | None) -> dict[str, Any]:
        rooms = self.rooms(identity)
        lines = [format_room_line(room, self.default_quality()) for room in rooms]
        username = re.sub(r"[^\w.@+-]", "_", self.identity_username(identity) or "admin").strip("_") or "user"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return {
            "filename": f"URL_config_{username}_{timestamp}.ini",
            "text": "\n".join(lines) + ("\n" if lines else ""),
            "count": len(lines),
        }

    def import_rooms(self, identity: dict[str, Any] | None, text: str) -> list[dict[str, Any]]:
        existing_rooms = self.all_rooms()
        for raw_line in iter_room_candidates(text):
            parsed_room = parse_room_line(raw_line, 0, self.default_quality())
            if parsed_room and parsed_room.get("valid"):
                parsed_room = normalize_room_payload(parsed_room, self.default_quality())
                self.assert_record_permission(identity, parsed_room["url"])
                existing_room = next(
                    (room for room in existing_rooms if room.get("url") == parsed_room["url"]),
                    None,
                )
                if existing_room:
                    self.assert_room_access(identity, existing_room)
        owner = "" if self.is_admin(identity) else self.identity_username(identity)
        return append_rooms(
            self.url_config_file,
            self.encoding,
            text,
            self.default_quality(),
            self.file_lock,
            owner,
        )

    def upsert_user(self, identity: dict[str, Any] | None, payload: dict[str, Any]) -> dict[str, Any]:
        self.assert_admin(identity)
        user = normalize_user_record(payload)
        if not user["username"]:
            raise ValueError("用户名不能为空")
        data = load_user_store(self.user_config_file)
        users = data.get("users", [])
        for index, current in enumerate(users):
            if current.get("username") == user["username"]:
                if not payload.get("password"):
                    user["password"] = current.get("password", "")
                if not payload.get("code"):
                    user["code"] = current.get("code", user["code"])
                if not user["password"]:
                    raise ValueError("用户密码不能为空")
                users[index] = user
                save_user_store(self.user_config_file, data)
                return public_user_record(user)
        if not user["password"]:
            raise ValueError("用户密码不能为空")
        users.append(user)
        data["users"] = users
        save_user_store(self.user_config_file, data)
        return public_user_record(user)

    def delete_user(self, identity: dict[str, Any] | None, username: str) -> None:
        self.assert_admin(identity)
        data = load_user_store(self.user_config_file)
        data["users"] = [
            user for user in data.get("users", [])
            if user.get("username") != username
        ]
        save_user_store(self.user_config_file, data)

    def visible_rooms(self, rooms: list[dict[str, Any]], identity: dict[str, Any] | None) -> list[dict[str, Any]]:
        if self.is_admin(identity):
            return rooms
        identifiers = self.identity_identifiers(identity)
        return [room for room in rooms if room.get("owner") in identifiers]

    def status(self, identity: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = self.status_provider()
        config_rooms = self.rooms(identity)
        configured_urls = {room.get("url") for room in config_rooms if room.get("url")}
        if configured_urls:
            payload["rooms"] = [
                room for room in payload.get("rooms", [])
                if room.get("url") in configured_urls
            ]
            payload["recording"] = [
                row for row in payload.get("recording", [])
                if row.get("url") in configured_urls
            ]
        else:
            payload["rooms"] = []
            payload["recording"] = []
        payload["user"] = self.user_payload(identity)
        status_by_url = {room.get("url"): dict(room) for room in payload.get("rooms", []) if room.get("url")}
        merged_rooms = []
        for room in config_rooms:
            url = room.get("url")
            if not url:
                continue
            status_room = status_by_url.get(url, {"url": url})
            status_room.setdefault("status", "queued" if room.get("enabled", True) else "disabled")
            status_room.setdefault("configured_name", room.get("name") or "")
            status_room["id"] = room.get("id")
            status_room["enabled"] = bool(room.get("enabled", True))
            status_room["configured_group"] = room.get("group") or ""
            status_room["group"] = room.get("group") or ""
            status_room["owner"] = room.get("owner") or ""
            status_room.setdefault("quality", room.get("quality") or self.default_quality())
            if not room.get("enabled", True):
                status_room["status"] = "disabled"
            merged_rooms.append(status_room)
        payload["rooms"] = merged_rooms
        enabled_urls = {room.get("url") for room in config_rooms if room.get("url") and room.get("enabled", True)}
        payload["monitoring"] = len(enabled_urls)
        payload["running_count"] = len(enabled_urls)
        payload["recording_count"] = len(payload.get("recording", []))
        if self.history_provider:
            payload["history"] = self.history_provider(
                list(payload.get("recording", [])),
                None if self.is_admin(identity) else configured_urls,
            )
        else:
            payload["history"] = {"updated_at": "", "ranges": {}}
        payload["running_urls"] = list(enabled_urls)
        payload["disabled_urls"] = [
            room.get("url") for room in config_rooms if room.get("url") and not room.get("enabled", True)
        ]
        payload.setdefault("server_time", datetime.datetime.now().isoformat(timespec="seconds"))
        now = datetime.datetime.now()
        next_checks = []
        for room in payload.get("rooms", []):
            next_check_at = str(room.get("next_check_at") or "")
            if not next_check_at:
                continue
            try:
                next_check_time = datetime.datetime.fromisoformat(next_check_at)
            except ValueError:
                continue
            if next_check_time <= now:
                continue
            next_checks.append(next_check_time)
        if next_checks:
            next_check_time = min(next_checks)
            payload["next_check_at"] = next_check_time.isoformat(timespec="seconds")
            payload["next_check_seconds"] = max(0, int((next_check_time - now).total_seconds() + 0.999))
        else:
            payload["next_check_at"] = ""
            payload["next_check_seconds"] = 0
        return payload

    def rooms(self, identity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.visible_rooms(
            read_rooms(self.url_config_file, self.encoding, self.default_quality()),
            identity,
        )

    def all_rooms(self) -> list[dict[str, Any]]:
        return read_rooms(self.url_config_file, self.encoding, self.default_quality())

    def config_sections(self, identity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.assert_admin(identity)
        return read_config_sections(self.config_file, self.encoding)

    def default_quality(self) -> str:
        quality = self.default_quality_provider() or "原画"
        return quality if quality in QUALITIES else "原画"

    def stop_runtime_urls(self, urls: list[str]) -> None:
        normalized_urls: list[str] = []
        for url in urls:
            if not url:
                continue
            normalized_url = normalize_url(str(url))
            if normalized_url:
                normalized_urls.append(normalized_url)
        if normalized_urls and self.runtime_stop_callback:
            self.runtime_stop_callback(normalized_urls)


def start_webui_server(
        host: str,
        port: int,
        app: RecorderWebUI,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    handler = make_handler(app)
    server = ResilientThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, name="webui-server", daemon=True)
    thread.start()
    return server, thread


def make_handler(app: RecorderWebUI):
    class WebUIRequestHandler(BaseHTTPRequestHandler):
        server_version = "DouyinLiveRecorderWebUI/0.41"

        def log_message(self, _format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self.send_text(build_static_html(), "text/html; charset=utf-8")
                return
            if path == "/api/auth":
                identity = self.identity()
                self.send_json({
                    "ok": True,
                    "authenticated": bool(identity),
                    "user": app.user_payload(identity) if identity else None,
                })
                return
            if not self.authorized():
                self.send_json({"ok": False, "message": "未授权"}, status=401)
                return
            identity = self.identity()
            if path == "/api/status":
                self.send_json({"ok": True, "data": app.status(identity)})
            elif path == "/api/rooms":
                self.send_json({"ok": True, "data": app.rooms(identity)})
            elif path == "/api/rooms/export":
                self.send_json({"ok": True, "data": app.export_rooms(identity)})
            elif path == "/api/admin-account":
                self.send_json({"ok": True, "data": app.admin_account(identity)})
            elif path == "/api/config":
                if not app.is_admin(identity):
                    self.send_json({"ok": False, "message": "需要管理员权限"}, status=403)
                    return
                self.send_json({"ok": True, "data": app.config_sections(identity)})
            elif path == "/api/users":
                if not app.is_admin(identity):
                    self.send_json({"ok": False, "message": "需要管理员权限"}, status=403)
                    return
                self.send_json({"ok": True, "data": app.managed_users(identity), "sites": PERMISSION_SITE_OPTIONS})
            else:
                self.send_json({"ok": False, "message": "Not found"}, status=404)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                body = self.read_json()
                if path == "/api/login":
                    username = str(body.get("username") or "")
                    password = str(body.get("password") or "")
                    identity = app.authenticate(username, password)
                    if not identity:
                        self.send_json({"ok": False, "message": "用户名或密码错误"}, status=401)
                        return
                    session_id = app.sessions.create(identity)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header(
                        "Set-Cookie",
                        f"DLR_WEBUI_SESSION={session_id}; Path=/; HttpOnly; SameSite=Lax; Max-Age={app.sessions.session_seconds}"
                    )
                    data = json.dumps({"ok": True, "user": app.user_payload(identity)}, ensure_ascii=False).encode("utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

                if path == "/api/logout":
                    app.sessions.delete(self.session_id())
                    data = json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Set-Cookie", "DLR_WEBUI_SESSION=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

                if not self.authorized():
                    self.send_json({"ok": False, "message": "未授权"}, status=401)
                    return
                identity = self.identity()

                if path == "/api/rooms":
                    if not app.is_admin(identity):
                        body["owner"] = app.identity_username(identity)
                    preview_room = normalize_room_payload(body, app.default_quality())
                    app.assert_record_permission(identity, str(preview_room.get("url") or ""))
                    existing_room = next(
                        (room for room in app.all_rooms() if room.get("url") == preview_room.get("url")),
                        None,
                    )
                    if existing_room:
                        app.assert_room_access(identity, existing_room)
                    room = append_room(
                        app.url_config_file, app.encoding, preview_room, app.default_quality(), app.file_lock
                    )
                    self.send_json({"ok": True, "data": room})
                elif path == "/api/rooms/preview":
                    room = normalize_room_payload(body, app.default_quality())
                    line = format_room_line(room, app.default_quality())
                    parsed = parse_room_line(line, 0, app.default_quality())
                    if not parsed or not parsed.get("valid"):
                        raise ValueError("直播间 URL 无效")
                    app.assert_record_permission(identity, parsed["url"])
                    self.send_json({"ok": True, "data": parsed})
                elif path == "/api/rooms/batch":
                    added = app.import_rooms(identity, str(body.get("text") or ""))
                    self.send_json({"ok": True, "data": added, "count": len(added)})
                elif path == "/api/rooms/import":
                    added = app.import_rooms(identity, str(body.get("text") or ""))
                    self.send_json({"ok": True, "data": added, "count": len(added)})
                elif path == "/api/recording/stop":
                    requested_url = str(body.get("url") or "")
                    current_room = next((room for room in app.all_rooms() if room.get("url") == normalize_url(requested_url)), {})
                    app.assert_room_access(identity, current_room)
                    app.stop_runtime_urls([requested_url])
                    try:
                        room = disable_room_by_url(
                            app.url_config_file,
                            app.encoding,
                            requested_url,
                            app.default_quality(),
                            app.file_lock,
                        )
                    except ValueError:
                        room = {"url": normalize_url(requested_url), "enabled": False}
                    self.send_json({"ok": True, "data": room})
                elif path == "/api/users":
                    self.send_json({"ok": True, "data": app.upsert_user(identity, body)})
                else:
                    self.send_json({"ok": False, "message": "Not found"}, status=404)
            except PermissionError as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=403)
            except Exception as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=400)

        def do_PUT(self) -> None:
            if not self.authorized():
                self.send_json({"ok": False, "message": "未授权"}, status=401)
                return
            path = urlparse(self.path).path
            try:
                body = self.read_json()
                room_match = re.match(r"^/api/rooms/(\d+)$", path)
                user_match = re.match(r"^/api/users/([^/]+)$", path)
                identity = self.identity()
                if room_match:
                    room_id = int(room_match.group(1))
                    before_rooms = app.all_rooms()
                    before_room = next((item for item in before_rooms if item.get("id") == room_id), {})
                    app.assert_room_access(identity, before_room)
                    if not app.is_admin(identity):
                        body["owner"] = app.identity_username(identity)
                    app.assert_record_permission(identity, str(body.get("url") or before_room.get("url") or ""))
                    room = update_room(
                        app.url_config_file,
                        app.encoding,
                        room_id,
                        body,
                        app.default_quality(),
                        app.file_lock,
                    )
                    stop_urls: list[str] = []
                    old_url = before_room.get("url")
                    new_url = room.get("url")
                    if old_url and old_url != new_url:
                        stop_urls.append(old_url)
                    if not bool(room.get("enabled", True)):
                        stop_urls.append(new_url)
                    app.stop_runtime_urls(stop_urls)
                    self.send_json({"ok": True, "data": room})
                elif path == "/api/admin-account":
                    account = app.update_admin_account(identity, body)
                    updated_identity = user_identity(account["username"], "admin")
                    app.sessions.replace_admin_sessions(self.session_id(), updated_identity)
                    self.send_json({"ok": True, "data": account, "user": app.user_payload(updated_identity)})
                elif path == "/api/config":
                    app.assert_admin(identity)
                    set_config_value(
                        app.config_file,
                        app.encoding,
                        str(body.get("section") or ""),
                        str(body.get("key") or ""),
                        str(body.get("value") or ""),
                        app.file_lock,
                    )
                    self.send_json({"ok": True})
                elif user_match:
                    body["username"] = user_match.group(1)
                    self.send_json({"ok": True, "data": app.upsert_user(identity, body)})
                else:
                    self.send_json({"ok": False, "message": "Not found"}, status=404)
            except PermissionError as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=403)
            except Exception as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=400)

        def do_PATCH(self) -> None:
            if not self.authorized():
                self.send_json({"ok": False, "message": "未授权"}, status=401)
                return
            path = urlparse(self.path).path
            try:
                body = self.read_json()
                identity = self.identity()
                if path == "/api/rooms/batch":
                    room_ids = [int(item) for item in body.get("ids", [])]
                    visible_ids = {int(room.get("id")) for room in app.rooms(identity)}
                    if not app.is_admin(identity):
                        room_ids = [room_id for room_id in room_ids if room_id in visible_ids]
                    changes = deepcopy(body.get("changes") or {})
                    if not app.is_admin(identity):
                        changes.pop("owner", None)
                        room_by_id = {int(room.get("id")): room for room in app.all_rooms()}
                        for room_id in room_ids:
                            current_room = room_by_id.get(room_id, {})
                            app.assert_room_access(identity, current_room)
                            if changes.get("enabled") is not False:
                                app.assert_record_permission(identity, str(current_room.get("url") or ""))
                    updated = patch_rooms(
                        app.url_config_file,
                        app.encoding,
                        room_ids,
                        changes,
                        app.default_quality(),
                        app.file_lock,
                    )
                    if changes.get("enabled") is False:
                        app.stop_runtime_urls([room.get("url") for room in updated])
                    self.send_json({"ok": True, "data": updated, "count": len(updated)})
                else:
                    self.send_json({"ok": False, "message": "Not found"}, status=404)
            except PermissionError as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=403)
            except Exception as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=400)

        def do_DELETE(self) -> None:
            if not self.authorized():
                self.send_json({"ok": False, "message": "未授权"}, status=401)
                return
            path = urlparse(self.path).path
            try:
                room_match = re.match(r"^/api/rooms/(\d+)$", path)
                user_match = re.match(r"^/api/users/([^/]+)$", path)
                identity = self.identity()
                if room_match:
                    room_id = int(room_match.group(1))
                    before_room = next((item for item in app.all_rooms() if item.get("id") == room_id), {})
                    app.assert_room_access(identity, before_room)
                    delete_room(app.url_config_file, app.encoding, room_id, app.file_lock)
                    app.stop_runtime_urls([before_room.get("url")])
                    self.send_json({"ok": True})
                elif user_match:
                    app.delete_user(identity, user_match.group(1))
                    self.send_json({"ok": True})
                else:
                    self.send_json({"ok": False, "message": "Not found"}, status=404)
            except PermissionError as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=403)
            except Exception as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=400)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def authorized(self) -> bool:
            return app.sessions.valid(self.session_id())

        def identity(self) -> dict[str, Any] | None:
            return app.sessions.get(self.session_id())

        def session_id(self) -> str:
            cookie_header = self.headers.get("Cookie") or ""
            for part in cookie_header.split(";"):
                key, _, value = part.strip().partition("=")
                if key == "DLR_WEBUI_SESSION":
                    return value
            return ""

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw or "{}")

        def send_text(self, text: str, content_type: str) -> None:
            payload = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return WebUIRequestHandler


WEBUI_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DouyinLiveRecorder WebUI</title>
  <style>
    :root {
      --bg: #f7f9fc;
      --panel: #ffffff;
      --panel-soft: #f8fbff;
      --text: #273449;
      --muted: #75849a;
      --line: #e6ebf3;
      --accent: #6f7df7;
      --accent-dark: #5262df;
      --green: #00c853;
      --amber: #ff9e52;
      --red: #f05d82;
      --cyan: #48bce8;
      --ink: #111827;
      --shadow: 0 18px 45px rgba(82, 98, 143, .12);
      --shadow-soft: 0 8px 22px rgba(82, 98, 143, .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        linear-gradient(180deg, #ffffff 0%, #f5f8fc 58%, #f4f7fb 100%);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Color Emoji", sans-serif;
    }
    body:not(.admin) [data-admin-only] {
      display: none !important;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      width: min(1320px, calc(100% - 24px));
      margin: 8px auto 0;
      padding: 10px 14px;
      border: 1px solid rgba(221, 227, 238, .9);
      border-radius: 8px;
      background: rgba(255, 255, 255, .92);
      position: sticky;
      top: 8px;
      z-index: 10;
      backdrop-filter: blur(14px);
      box-shadow: var(--shadow-soft);
    }
    body:not(.authenticated) header,
    body:not(.authenticated) main {
      display: none;
    }
    h1 {
      font-size: 18px;
      margin: 0;
      font-weight: 680;
      letter-spacing: 0;
    }
    main {
      width: min(1320px, 100%);
      margin: 0 auto;
      padding: 18px 12px 28px;
    }
    .topline {
      display: flex;
      align-items: center;
      gap: 9px;
      color: var(--muted);
      min-width: 0;
    }
    .brand-mark {
      display: grid;
      place-items: center;
      width: 30px;
      height: 30px;
      border-radius: 8px;
      background: #eef2ff;
      color: var(--accent);
      border: 1px solid #dce2ff;
      font-size: 12px;
      font-weight: 800;
      flex: 0 0 auto;
    }
    .tabs {
      display: flex;
      gap: 6px;
      padding: 3px;
      border: 1px solid #e5eaf5;
      background: #f4f7fc;
      border-radius: 8px;
    }
    .tab {
      border: 0;
      background: transparent;
      color: #344054;
      padding: 7px 13px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 650;
    }
    .tab.active {
      background: var(--panel);
      color: var(--accent);
      box-shadow: 0 5px 14px rgba(111, 125, 247, .14);
    }
    .login-screen {
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      background:
        linear-gradient(180deg, rgba(17, 24, 39, .06), rgba(17, 24, 39, 0) 34%),
        var(--bg);
    }
    body.authenticated .login-screen {
      display: none;
    }
    .login-panel {
      width: min(420px, 100%);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 24px;
    }
    .login-panel h2 {
      margin: 0 0 6px;
      font-size: 21px;
      letter-spacing: 0;
    }
    .login-panel p {
      margin: 0 0 18px;
      color: var(--muted);
    }
    .login-field {
      display: grid;
      gap: 6px;
      margin-bottom: 12px;
    }
    .login-field label {
      color: #344054;
      font-weight: 650;
      font-size: 13px;
    }
    .login-actions {
      display: grid;
      gap: 10px;
      margin-top: 16px;
    }
    .login-error {
      min-height: 20px;
      color: var(--red);
      font-weight: 650;
    }
    .view { display: none; }
    .view.active { display: block; }
    .band {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow-soft);
      margin-bottom: 14px;
      overflow: hidden;
    }
    .band-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 48px;
      padding: 11px 14px;
      border-bottom: 1px solid #cbd7e3;
      background: linear-gradient(180deg, #f3f7fb 0%, #eaf1f7 100%);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, .8);
    }
    .band-title {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      font-size: 15px;
      font-weight: 700;
      color: #21384c;
    }
    .band-title::before {
      content: "";
      width: 4px;
      height: 18px;
      border-radius: 999px;
      background: var(--accent);
      flex: 0 0 auto;
    }
    .band-head .muted,
    .band-head label {
      color: #475569;
      font-weight: 650;
    }
    .dashboard {
      display: grid;
      gap: 18px;
    }
    .home-shell {
      padding: 8px;
      border: 1px solid rgba(219, 225, 236, .9);
      border-radius: 8px;
      background: rgba(255, 255, 255, .86);
      box-shadow: 0 14px 38px rgba(85, 97, 130, .09);
    }
    .dashboard-titlebar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      min-height: 34px;
      padding: 2px 2px 0;
    }
    .dashboard-titlebar > div:first-child {
      min-width: 0;
    }
    .dashboard-titlebar h2 {
      margin: 0;
      color: #263247;
      font-size: 15px;
      font-weight: 800;
      letter-spacing: 0;
    }
    .dashboard-subtitle {
      margin-left: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    #dashboardCopy {
      display: block;
      max-width: min(680px, 100%);
      margin-left: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .home-actions {
      display: inline-flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }
    .home-actions button {
      min-height: 30px;
      padding: 5px 10px;
      border-color: #d8e0ec;
      border-radius: 999px;
      background: rgba(255, 255, 255, .86);
      color: #53627a;
      font-size: 12px;
      box-shadow: none;
    }
    .home-actions button.primary {
      border-color: #cfdaff;
      background: #eaf0ff;
      color: #5262df;
    }
    .home-actions button.danger {
      border-color: #ffd6df;
      background: #fff1f4;
      color: #dc4c70;
    }
    .home-stat-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .home-stat-card {
      position: relative;
      min-height: 86px;
      overflow: hidden;
      border: 1px solid rgba(226, 232, 243, .9);
      border-radius: 8px;
      padding: 14px 18px 12px;
      background: #f3f6ff;
      box-shadow: 0 10px 22px rgba(95, 109, 154, .07);
    }
    .home-stat-card::after {
      content: "";
      position: absolute;
      right: -4px;
      bottom: -14px;
      width: 82px;
      height: 64px;
      border: 7px solid rgba(255, 255, 255, .34);
      border-radius: 16px;
      transform: rotate(-9deg);
    }
    .home-stat-card.card-blue { background: linear-gradient(135deg, #dfe8ff 0%, #edf3ff 100%); }
    .home-stat-card.card-purple { background: linear-gradient(135deg, #eee2ff 0%, #f6edff 100%); }
    .home-stat-card.card-orange { background: linear-gradient(135deg, #ffe6cf 0%, #fff1dd 100%); }
    .home-stat-card.card-indigo { background: linear-gradient(135deg, #dfe5ff 0%, #edf0ff 100%); }
    .home-stat-card span {
      display: block;
      color: #6278b3;
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 7px;
    }
    .home-stat-card strong {
      position: relative;
      z-index: 1;
      display: block;
      color: #1f2739;
      font-size: clamp(24px, 3vw, 32px);
      line-height: 1;
      letter-spacing: 0;
      font-variant-numeric: tabular-nums;
    }
    .home-stat-card em {
      position: relative;
      z-index: 1;
      display: block;
      margin-top: 6px;
      color: rgba(73, 86, 114, .72);
      font-style: normal;
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .overview-band {
      margin-bottom: 0;
      border-radius: 8px;
      box-shadow: var(--shadow-soft);
    }
    .overview-band .band-head {
      align-items: center;
      border-bottom-color: transparent;
      background: #fff;
      flex-wrap: nowrap;
    }
    .overview-head-main {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
      flex: 1 1 auto;
      overflow: hidden;
    }
    .overview-head-main .band-title {
      flex: 0 0 auto;
    }
    .overview-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      padding: 0 10px 10px;
    }
    .donut-card {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      min-height: 270px;
      border: 1px solid #e6ebf3;
      border-radius: 8px;
      background: #fff;
      box-shadow: var(--shadow-soft);
      overflow: hidden;
    }
    .donut-card-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 42px;
      padding: 10px 20px 4px;
    }
    .donut-card-head h3 {
      margin: 0;
      color: #314052;
      font-size: 13px;
      font-weight: 800;
    }
    .donut-card-head span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .donut-layout {
      display: grid;
      grid-template-columns: minmax(140px, .9fr) minmax(180px, 1fr);
      align-items: center;
      gap: 18px;
      min-height: 220px;
      padding: 12px 28px 28px;
    }
    .donut-chart {
      display: grid;
      place-items: center;
      justify-self: center;
      width: min(154px, 34vw);
      aspect-ratio: 1;
      border-radius: 50%;
      background: var(--donut-bg, #eaf0f7);
      position: relative;
      box-shadow: 0 10px 28px rgba(96, 84, 214, .18);
    }
    .donut-chart::before {
      content: "";
      position: absolute;
      inset: 32%;
      border-radius: 50%;
      background: #fff;
      box-shadow: inset 0 0 0 1px #edf1f6;
    }
    .donut-hole {
      position: relative;
      z-index: 1;
      display: grid;
      place-items: center;
      gap: 2px;
      text-align: center;
    }
    .donut-hole strong {
      display: block;
      color: #28364d;
      font-size: 20px;
      line-height: 1;
      font-variant-numeric: tabular-nums;
    }
    .donut-hole span {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }
    .legend-list {
      display: grid;
      gap: 9px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .legend-item {
      display: grid;
      grid-template-columns: 10px minmax(0, 1fr) auto;
      align-items: center;
      gap: 8px;
      color: #5d6b80;
      font-size: 13px;
      font-weight: 650;
      min-width: 0;
    }
    .legend-dot {
      width: 9px;
      height: 9px;
      border-radius: 3px;
      background: var(--dot-color, var(--accent));
    }
    .legend-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .legend-value {
      color: #40506a;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }
	    .home-lower-grid {
	      display: grid;
	      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
	      gap: 10px;
	      align-items: stretch;
	    }
	    .mini-panel {
	      display: flex;
	      flex-direction: column;
	      height: 596px;
	      margin-bottom: 0;
	      min-height: 240px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, .9);
      box-shadow: var(--shadow-soft);
      overflow: hidden;
    }
    .mini-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 42px;
      padding: 11px 14px 7px;
    }
    .summary-pills {
      display: flex;
      align-items: center;
      gap: 5px;
      flex: 1 1 auto;
      flex-wrap: nowrap;
      min-width: 0;
      overflow-x: auto;
      padding: 0 2px;
      background: transparent;
      scrollbar-width: none;
    }
    .summary-pills::-webkit-scrollbar {
      display: none;
    }
    .summary-pills .pill {
      min-height: 20px;
      padding: 2px 7px;
      font-size: 11px;
      white-space: nowrap;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 8px;
      border-radius: 999px;
      color: #475569;
      background: var(--panel-soft);
      border: 1px solid #e2e8f0;
      font-size: 12px;
      font-weight: 700;
    }
    .pill.good { color: #037a36; background: #dffbea; border-color: #6ee7a8; }
    .pill.warn { color: var(--amber); background: #fff7ed; border-color: #f4dfc1; }
    .pill.bad { color: var(--red); background: #fff3f2; border-color: #efd2cf; }
    .pill.info { color: var(--cyan); background: #eef8f9; border-color: #d5e9ec; }
    .pill.resource { color: #41516a; background: #f7fbff; border-color: #dbe6f2; }
	    .recent-panel-body {
	      display: flex;
	      flex: 1;
	      flex-direction: column;
	      min-height: 0;
	      padding: 0 10px 10px;
	    }
	    .recent-card-list {
	      display: grid;
	      align-content: start;
	      flex: 1;
	      gap: 4px;
	      min-height: 0;
	      overflow: hidden;
	      padding-right: 0;
	    }
    .recent-card {
      position: relative;
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 6px;
      align-items: center;
      box-sizing: border-box;
      height: 44px;
      min-height: 44px;
      padding: 4px 6px;
      border: 1px solid #e6ebf3;
      border-radius: 7px;
      background: #fff;
      overflow: hidden;
    }
    .recent-card.recording {
      border-color: #9fb2ff;
      background: linear-gradient(180deg, #f4f7ff 0%, #ffffff 100%);
      box-shadow: 0 6px 16px rgba(92, 111, 232, .10);
    }
	    .recent-avatar-wrap {
	      position: relative;
	      display: grid;
	      place-items: center;
	      width: 26px;
	      height: 26px;
	      margin: 0 auto;
	      border: 1px solid #dbe6f7;
	      border-radius: 50%;
	      background: linear-gradient(135deg, #dbe7ff 0%, #8193ff 48%, #39b8e6 100%);
	      box-shadow: 0 5px 12px rgba(100, 115, 255, .14);
	      color: #fff;
	      font-size: 11px;
	      font-weight: 900;
	      overflow: visible;
	      z-index: 3;
	    }
	    .recent-card.recording .recent-avatar-wrap {
	      border-color: #6d7cff;
	      box-shadow: 0 0 0 2px rgba(109, 124, 255, .12), 0 6px 14px rgba(80, 105, 220, .16);
	    }
	    .recent-avatar {
	      position: absolute;
	      inset: 0;
	      width: 100%;
	      height: 100%;
	      border-radius: inherit;
	      object-fit: cover;
	      z-index: 1;
	    }
	    .recent-avatar-fallback {
	      position: relative;
	      z-index: 0;
	      line-height: 1;
	    }
    .recent-detail {
      display: grid;
      align-content: center;
      gap: 3px;
      min-width: 0;
      overflow: hidden;
    }
    .recent-title-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }
    .recent-title {
      margin: 0;
      overflow: hidden;
      color: #2b3749;
      font-size: 12px;
      font-weight: 850;
      line-height: 1.08;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .recent-card .status {
      justify-content: center;
      gap: 0;
      min-height: 16px;
      min-width: 36px;
      padding: 1px 4px;
      font-size: 10px;
      line-height: 1.25;
      text-align: center;
      white-space: nowrap;
    }
    .recent-meta-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0 8px;
      color: #627086;
      font-size: 10px;
      line-height: 1.1;
      min-width: 0;
    }
    .recent-meta-grid span {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .recent-actions {
      position: absolute;
      top: 50%;
      left: 23px;
      z-index: 4;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      transform: translate(-50%, -50%);
      opacity: 0;
      pointer-events: none;
      transition: opacity .16s ease;
    }
    .recent-avatar-wrap:hover ~ .recent-actions,
    .recent-avatar-wrap:focus-within ~ .recent-actions,
    .recent-actions:hover,
    .recent-actions:focus-within {
      opacity: 1;
      pointer-events: auto;
    }
    .recent-action-trigger,
    .recent-room-action {
      min-height: 20px;
      border-radius: 5px;
      font-size: 10px;
      line-height: 1;
    }
    .recent-action-trigger {
      width: 22px;
      padding: 0;
      color: #3b4760;
      background: rgba(255, 255, 255, .94);
      box-shadow: 0 4px 10px rgba(63, 74, 96, .16);
    }
    .recent-action-list {
      display: none;
      align-items: center;
      gap: 3px;
      padding: 2px;
      border: 1px solid #dbe3ef;
      border-radius: 6px;
      background: rgba(255, 255, 255, .98);
      box-shadow: 0 8px 18px rgba(55, 66, 89, .16);
    }
    .recent-actions:hover .recent-action-list,
    .recent-actions:focus-within .recent-action-list {
      display: inline-flex;
    }
    .recent-room-action {
      padding: 2px 5px;
      white-space: nowrap;
    }
    .recent-room-action.danger {
      color: #fff;
      border-color: var(--red);
      background: var(--red);
    }
    .recent-summary {
      display: none;
    }
	    .monitor-pager {
	      display: flex;
	      align-items: center;
	      justify-content: space-between;
	      gap: 8px;
	      padding-top: 6px;
	      color: var(--muted);
	      font-size: 11px;
	      font-weight: 750;
	    }
	    .monitor-pager button {
	      min-height: 24px;
	      padding: 3px 8px;
	      font-size: 11px;
	    }
    .panel-body {
      padding: 10px 16px 16px;
    }
    .range-tabs {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex: 0 0 auto;
      padding: 3px;
      border: 1px solid #d8e2eb;
      border-radius: 8px;
      background: rgba(255, 255, 255, .72);
    }
    .range-tab {
      min-height: 28px;
      padding: 4px 9px;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: #475569;
      font-size: 12px;
      font-weight: 800;
    }
    .range-tab:hover {
      background: #edf4fb;
      border-color: transparent;
    }
    .range-tab.active {
      background: #dce5ff;
      color: #5262df;
    }
    .trend-compact .trend-summary {
      grid-template-columns: 1fr;
      gap: 6px;
      padding-bottom: 8px;
    }
    .trend-compact .trend-summary-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 28px;
      padding: 5px 8px;
      border-radius: 6px;
    }
    .trend-compact .trend-summary-item strong {
      margin-top: 0;
      font-size: 14px;
    }
    .trend-compact .trend-list {
      gap: 7px;
    }
	    .trend-compact .trend-row {
	      grid-template-columns: 46px minmax(72px, 1fr) max-content;
	      gap: 7px;
	      min-height: 22px;
	    }
	    .trend-compact .trend-value {
	      max-width: none;
	      overflow: visible;
	      text-align: right;
	    }
    .trend-summary {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      padding-bottom: 12px;
    }
    .trend-summary-item {
      min-width: 0;
      padding: 10px 11px;
      border: 1px solid #e1e8f2;
      border-radius: 8px;
      background: #f8fbfe;
    }
    .trend-summary-item span {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 750;
    }
    .trend-summary-item strong {
      display: block;
      margin-top: 5px;
      color: #26384f;
      font-size: 18px;
      line-height: 1.15;
      font-variant-numeric: tabular-nums;
    }
    .trend-list {
      display: grid;
      gap: 9px;
    }
	    .trend-row {
	      display: grid;
	      grid-template-columns: 70px minmax(86px, 1fr) max-content;
	      gap: 10px;
	      align-items: center;
	      min-height: 28px;
    }
    .trend-date {
      color: #405a72;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
    }
    .trend-track {
      height: 9px;
      border-radius: 999px;
      background: #e8edf4;
      overflow: hidden;
    }
	    .trend-fill {
	      height: 100%;
	      min-width: 3px;
	      border-radius: 999px;
	      background: var(--trend-fill, linear-gradient(90deg, #9fb9ff, #7dd7c2));
	      box-shadow: 0 0 10px var(--trend-glow, rgba(111, 125, 247, .08));
    }
    .trend-value {
      color: #40506a;
      font-size: 12px;
      font-weight: 800;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }
    .rank-list {
      display: grid;
      gap: 7px;
      padding-top: 2px;
    }
	    .rank-row {
	      display: grid;
	      grid-template-columns: minmax(150px, 1fr) minmax(72px, .6fr) 62px;
	      gap: 10px;
	      align-items: center;
	      min-height: 42px;
	      padding: 5px 8px;
	      border: 1px solid #e7ecf4;
	      border-radius: 8px;
	      background: #fff;
	      font-size: 12px;
	    }
	    .rank-profile {
	      display: grid;
	      grid-template-columns: 30px minmax(0, 1fr);
	      align-items: center;
	      gap: 8px;
	      min-width: 0;
	    }
	    .rank-avatar {
	      width: 30px;
	      height: 30px;
	      border: 1px solid #dce5f1;
	      border-radius: 50%;
	      background: linear-gradient(135deg, #eef4ff 0%, #e7fbf3 100%);
	      color: #60708a;
	      object-fit: cover;
	      overflow: hidden;
	    }
	    .rank-avatar.fallback {
	      display: grid;
	      place-items: center;
	      font-size: 12px;
	      font-weight: 850;
	    }
	    .rank-avatar.hidden {
	      display: none;
	    }
	    .rank-name {
	      overflow: hidden;
	      text-overflow: ellipsis;
	      white-space: nowrap;
      font-weight: 800;
    }
    .rank-track {
      height: 5px;
      border-radius: 999px;
      background: #edf1f7;
      overflow: hidden;
    }
    .rank-fill {
      height: 100%;
      min-width: 3px;
      border-radius: 999px;
      background: #6f7df7;
    }
    .rank-value {
      color: #40506a;
      font-weight: 850;
      text-align: right;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }
    .rank-detail {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
    }
    .chart-bars {
      display: grid;
      align-items: end;
      grid-template-columns: repeat(5, minmax(42px, 1fr));
      gap: 14px;
      min-height: 220px;
      padding-top: 8px;
    }
    .chart-bar-item {
      display: grid;
      grid-template-rows: 1fr auto auto;
      gap: 7px;
      min-width: 0;
      height: 220px;
    }
    .chart-bar-track {
      display: flex;
      align-items: flex-end;
      min-height: 156px;
      border-radius: 8px;
      background: #edf3f9;
      overflow: hidden;
    }
    .chart-bar-fill {
      width: 100%;
      min-height: 3px;
      border-radius: 8px 8px 0 0;
      background: var(--accent);
    }
    .chart-bar-fill.good { background: var(--green); }
    .chart-bar-fill.warn { background: var(--amber); }
    .chart-bar-fill.info { background: var(--cyan); }
    .chart-bar-fill.bad { background: var(--red); }
    .chart-bar-label,
    .chart-bar-value {
      text-align: center;
      font-size: 12px;
      font-weight: 700;
      color: #476174;
      white-space: nowrap;
    }
    .chart-bar-value {
      color: var(--text);
      font-variant-numeric: tabular-nums;
    }
    .anchor-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(140px, 1fr));
      gap: 10px;
    }
    .anchor-card {
      display: grid;
      gap: 8px;
      min-height: 86px;
      padding: 10px;
      border: 1px solid #d8e2eb;
      border-radius: 8px;
      background: #fff;
      box-shadow: var(--shadow-soft);
    }
    .anchor-card-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-width: 0;
      font-weight: 800;
    }
    .anchor-card-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .anchor-card-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .metric-chip {
      display: inline-flex;
      align-items: center;
      min-height: 20px;
      padding: 2px 7px;
      border-radius: 999px;
      background: #edf4ff;
      color: var(--accent);
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }
    .monitor-band {
      margin-bottom: 0;
    }
    .monitor-table td {
      height: 46px;
    }
    .monitor-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-weight: 750;
    }
    .monitor-name small {
      display: block;
      overflow: hidden;
      margin-top: 2px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .monitor-action {
      text-align: right;
    }
    .monitor-row-actions {
      display: flex;
      justify-content: flex-end;
      gap: 4px;
      white-space: nowrap;
    }
    .monitor-row-actions button {
      min-height: 24px;
      padding: 3px 6px;
      font-size: 11px;
    }
    .rooms-workspace {
      display: grid;
      gap: 12px;
      padding: 8px;
      border: 1px solid rgba(219, 225, 236, .9);
      border-radius: 8px;
      background: rgba(255, 255, 255, .86);
      box-shadow: 0 14px 38px rgba(85, 97, 130, .09);
    }
    .rooms-page-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      min-height: 38px;
      padding: 2px 2px 0;
    }
    .rooms-page-title {
      min-width: 0;
    }
    .rooms-page-title h2 {
      margin: 0;
      color: #263247;
      font-size: 15px;
      font-weight: 850;
      letter-spacing: 0;
    }
    .rooms-page-title span {
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .rooms-actions {
      display: inline-flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }
    .rooms-actions button {
      min-height: 32px;
      padding: 6px 10px;
      border-color: #d8e0ec;
      border-radius: 999px;
      background: rgba(255, 255, 255, .9);
      color: #53627a;
      font-size: 12px;
    }
    .rooms-metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }
    .rooms-metric-card {
      position: relative;
      min-height: 76px;
      overflow: hidden;
      border: 1px solid rgba(226, 232, 243, .9);
      border-radius: 8px;
      padding: 12px 16px;
      background: #f4f7ff;
      box-shadow: 0 10px 22px rgba(95, 109, 154, .07);
    }
    .rooms-metric-card::after {
      content: "";
      position: absolute;
      right: -16px;
      bottom: -22px;
      width: 82px;
      height: 82px;
      border: 8px solid rgba(255, 255, 255, .35);
      border-radius: 50%;
    }
    .rooms-metric-card.card-blue { background: linear-gradient(135deg, #e0e9ff 0%, #f0f5ff 100%); }
    .rooms-metric-card.card-green { background: linear-gradient(135deg, #dff7ef 0%, #effbf7 100%); }
    .rooms-metric-card.card-orange { background: linear-gradient(135deg, #ffe8cf 0%, #fff3e2 100%); }
    .rooms-metric-card.card-purple { background: linear-gradient(135deg, #eee4ff 0%, #f7efff 100%); }
    .rooms-metric-card span {
      display: block;
      color: #64779a;
      font-size: 12px;
      font-weight: 800;
      margin-bottom: 6px;
    }
    .rooms-metric-card strong {
      position: relative;
      z-index: 1;
      display: block;
      color: #1f2739;
      font-size: 28px;
      line-height: 1;
      font-variant-numeric: tabular-nums;
    }
    .rooms-metric-card em {
      position: relative;
      z-index: 1;
      display: block;
      margin-top: 6px;
      overflow: hidden;
      color: rgba(73, 86, 114, .72);
      font-size: 12px;
      font-style: normal;
      font-weight: 650;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .rooms-command-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(310px, .75fr);
      gap: 10px;
      align-items: stretch;
    }
    .room-command-card,
    .room-list-card {
      display: flex;
      flex-direction: column;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, .92);
      box-shadow: var(--shadow-soft);
      overflow: hidden;
    }
    .room-command-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 42px;
      padding: 11px 14px 7px;
      border-bottom: 1px solid #edf1f7;
    }
    .room-command-title {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0;
      color: #314052;
      font-size: 14px;
      font-weight: 850;
    }
    .room-command-title::before {
      content: "";
      width: 4px;
      height: 16px;
      border-radius: 999px;
      background: var(--accent);
      flex: 0 0 auto;
    }
    .room-command-head .muted {
      font-size: 12px;
      font-weight: 650;
    }
    .room-command-body {
      flex: 1;
      padding: 14px;
    }
    .room-filterbar {
      display: grid;
      grid-template-columns: minmax(240px, 1fr) minmax(130px, 170px) minmax(130px, 160px) minmax(118px, 140px) auto auto;
      gap: 10px;
      align-items: center;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }
    .room-list-summary {
      grid-column: 1 / -1;
      justify-self: start;
      white-space: nowrap;
      font-weight: 650;
    }
    .room-table-wrap {
      flex: 1;
      border-top: 1px solid var(--line);
    }
    .rooms-table th {
      background: #f7faff;
      color: #718099;
      font-size: 11px;
      letter-spacing: 0;
    }
    .rooms-table td {
      height: 52px;
      padding: 8px 9px;
      background: #fff;
    }
    .rooms-table tbody tr:hover td {
      background: #fafcff;
    }
    .rooms-table input,
    .rooms-table select {
      min-height: 32px;
      padding: 6px 8px;
      border-color: #dce3ee;
      background: #fbfdff;
      font-size: 13px;
    }
    .rooms-table input[type="checkbox"] {
      width: 18px;
      height: 18px;
      min-height: 18px;
      padding: 0;
    }
	    .rooms-table .row-actions button {
	      min-height: 30px;
	      padding: 5px 8px;
	      font-size: 12px;
	    }
	    .room-anchor-cell {
	      display: grid;
	      grid-template-columns: 32px minmax(0, 1fr);
	      align-items: center;
	      gap: 8px;
	      min-width: 0;
	    }
	    .room-anchor-avatar {
	      width: 32px;
	      height: 32px;
	    }
	    .room-avatar {
	      width: 32px;
	      height: 32px;
	      border: 1px solid #dfe7f3;
	      border-radius: 50%;
	      background: linear-gradient(135deg, #eef4ff 0%, #e7fbf3 100%);
	      color: #60708a;
	      object-fit: cover;
	      overflow: hidden;
	    }
	    .room-avatar.fallback {
	      display: grid;
	      place-items: center;
	      font-size: 12px;
	      font-weight: 850;
	    }
	    .room-avatar.hidden {
	      display: none;
	    }
	    .room-anchor-cell input {
	      min-width: 0;
	    }
	    .pager {
	      display: flex;
	      align-items: center;
	      justify-content: flex-end;
      gap: 8px;
      padding: 10px 14px;
      border-top: 1px solid var(--line);
      background: var(--panel-soft);
    }
    .pager-info {
      color: var(--muted);
      min-width: 120px;
      text-align: center;
      font-weight: 650;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: middle;
      word-break: break-word;
    }
    th {
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
      background: var(--panel-soft);
    }
    th.sortable-th {
      padding: 0;
    }
    .sort-button {
      display: inline-flex;
      align-items: center;
      justify-content: flex-start;
      gap: 4px;
      width: 100%;
      min-height: 40px;
      padding: 10px 12px;
      border: 0;
      border-radius: 0;
      background: transparent;
      color: inherit;
      font-size: 12px;
      font-weight: 700;
      text-align: left;
    }
    .sort-button:hover {
      background: #eaf2f9;
      border-color: transparent;
    }
    .sort-button.active {
      color: var(--accent);
    }
    .sort-indicator {
      min-width: 12px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1;
    }
    tr:last-child td { border-bottom: 0; }
    .url-cell {
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 13px;
    }
    .time-cell {
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid #cbd3df;
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      padding: 8px 9px;
      font: inherit;
      min-height: 36px;
    }
    textarea {
      min-height: 132px;
      resize: vertical;
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      line-height: 1.5;
    }
    input[type="checkbox"] {
      width: 18px;
      height: 18px;
      min-height: 18px;
      accent-color: var(--accent);
    }
    button {
      border: 1px solid #b9c4d3;
      background: #fff;
      color: var(--text);
      border-radius: 6px;
      padding: 8px 11px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
      min-height: 36px;
      white-space: nowrap;
      transition: background .15s ease, border-color .15s ease, transform .15s ease;
    }
    button:hover {
      border-color: #94a3b8;
      background: #f8fafc;
    }
    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #fff;
    }
    button.primary:hover {
      border-color: var(--accent-dark);
      background: var(--accent-dark);
    }
    .hero-actions button:hover {
      border-color: #94a8ba;
      background: #f8fafc;
      color: var(--text);
    }
    .hero-actions button.primary:hover {
      border-color: var(--accent-dark);
      background: var(--accent-dark);
      color: #fff;
    }
    .hero-actions button.danger:hover {
      border-color: #d89d98;
      background: #fff0ef;
      color: var(--red);
    }
    button.danger {
      border-color: #f1b7ba;
      color: var(--red);
      background: #fff6f6;
    }
    button:disabled {
      opacity: .52;
      cursor: not-allowed;
    }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(92px, 112px) minmax(108px, 130px) minmax(120px, 150px) minmax(120px, 150px) minmax(260px, 1fr) minmax(140px, 180px) auto;
      gap: 10px;
      padding: 0;
      border-bottom: 0;
      align-items: end;
    }
    .room-command-card .toolbar {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .room-command-card .toolbar .form-field:nth-child(5) {
      grid-column: span 2;
    }
    .room-command-card .toolbar .room-add-submit {
      width: 100%;
    }
    .batch {
      display: grid;
      grid-template-rows: minmax(158px, 1fr) auto;
      gap: 10px;
      height: 100%;
      padding: 0;
      border-top: 0;
    }
    .batch textarea {
      min-height: 158px;
    }
    .batch button {
      min-height: 44px;
    }
    .bulkbar {
      display: grid;
      grid-template-columns: minmax(96px, 125px) minmax(96px, 125px) minmax(108px, 132px) minmax(130px, 1fr) minmax(106px, 128px) minmax(106px, 128px) minmax(150px, 1fr) auto auto;
      gap: 10px;
      padding: 14px;
      border-bottom: 0;
      align-items: end;
      background: transparent;
    }
    .room-toggle-group {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      grid-column: 1 / -1;
      min-height: 36px;
    }
    .room-add-submit {
      align-self: end;
      min-width: 88px;
    }
    .form-field {
      display: grid;
      gap: 5px;
      min-width: 0;
    }
    .form-field > span {
      color: #475569;
      font-size: 12px;
      font-weight: 700;
      line-height: 1;
    }
    .check-field {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 36px;
      color: #344054;
      font-weight: 650;
      white-space: nowrap;
    }
    .check-field input {
      flex: 0 0 auto;
    }
    .band-actions {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .priority-hint {
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .room-priority {
      min-width: 106px;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 24px;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      background: #edf2f7;
      color: #344054;
    }
    .status.recording {
      background: linear-gradient(135deg, #5c6cff 0%, #21a7d8 100%);
      color: #fff;
      box-shadow: 0 6px 14px rgba(80, 105, 220, .22);
    }
    .status.waiting { background: #fff4e5; color: var(--amber); }
    .status.error { background: #fff0f0; color: var(--red); }
    .status.checking { background: #e8f7fa; color: var(--cyan); }
    .status.disabled { background: #f0f2f5; color: #667085; }
    .muted { color: var(--muted); }
    .row-actions {
      display: flex;
      gap: 7px;
      align-items: center;
      justify-content: flex-end;
    }
    .config-layout {
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      min-height: 560px;
      background: var(--panel-soft);
    }
    .section-list {
      border-right: 1px solid var(--line);
      padding: 10px;
      background: #eef4f9;
    }
    .section-btn {
      display: block;
      width: 100%;
      text-align: left;
      margin-bottom: 6px;
      border-color: transparent;
      background: transparent;
    }
    .section-btn.active {
      border-color: #cbd3df;
      background: #fff;
      color: var(--accent);
    }
    .config-cards {
      display: grid;
      grid-template-columns: repeat(2, minmax(320px, 1fr));
      gap: 12px;
      align-content: start;
      padding: 12px;
    }
    .config-card {
      display: flex;
      flex-direction: column;
      min-width: 0;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow-soft);
      overflow: hidden;
    }
    .config-card.wide {
      grid-column: 1 / -1;
    }
    .config-card-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 44px;
      padding: 10px 12px;
      border-bottom: 1px solid #d8e2eb;
      background: linear-gradient(180deg, #f7fbff 0%, #edf4fa 100%);
    }
    .config-card-title {
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      font-size: 14px;
      font-weight: 800;
      color: #21384c;
    }
    .config-card-title::before {
      content: "";
      width: 4px;
      height: 16px;
      border-radius: 999px;
      background: var(--accent);
      flex: 0 0 auto;
    }
    .config-card-title small {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .config-card-body {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 12px;
      padding: 12px;
    }
    .config-field {
      display: grid;
      gap: 6px;
      min-width: 0;
    }
    .config-field.long {
      grid-column: 1 / -1;
    }
    .config-field label {
      color: #344054;
      font-size: 12px;
      font-weight: 700;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .config-field textarea {
      min-height: 88px;
    }
    .config-hint {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .config-hint.warn {
      color: var(--amber);
      font-weight: 700;
    }
    .save-config-group {
      min-height: 32px;
      padding: 6px 10px;
    }
    .config-table input[type="password"],
    .config-table input[type="text"] {
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 13px;
    }
	    .user-toolbar {
	      display: grid;
	      grid-template-columns: minmax(130px, 180px) minmax(130px, 180px) minmax(180px, 1fr) 86px auto auto;
	      gap: 10px;
	      align-items: end;
      padding: 14px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }
    .permission-panel {
      display: grid;
      gap: 10px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-soft);
    }
    .site-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
      gap: 7px 10px;
    }
    .site-check {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 32px;
      padding: 5px 8px;
      border: 1px solid #d8e2eb;
      border-radius: 6px;
      background: #fff;
      color: #344054;
      font-weight: 650;
    }
    .site-check input {
      flex: 0 0 auto;
    }
	    .user-permissions {
	      min-width: 190px;
	    }
	    .permission-summary {
	      display: grid;
	      grid-template-columns: minmax(0, 1fr) auto;
	      gap: 8px;
	      align-items: center;
	    }
	    .permission-summary-text {
	      overflow: hidden;
	      color: #344054;
	      font-weight: 650;
	      text-overflow: ellipsis;
	      white-space: nowrap;
	    }
	    .permission-summary button {
	      min-height: 32px;
	      padding: 5px 9px;
	    }
	    .site-editor-backdrop {
	      position: fixed;
	      inset: 0;
	      z-index: 40;
	      display: flex;
	      align-items: center;
	      justify-content: center;
	      padding: 18px;
	      background: rgba(15, 23, 42, .36);
	    }
	    .site-editor-backdrop[hidden] {
	      display: none;
	    }
	    .site-editor-dialog {
	      display: grid;
	      grid-template-rows: auto minmax(0, 1fr) auto;
	      width: min(760px, 100%);
	      max-height: min(82vh, 720px);
	      overflow: hidden;
	      border: 1px solid #cbd7e3;
	      border-radius: 8px;
	      background: #fff;
	      box-shadow: 0 22px 54px rgba(15, 23, 42, .26);
	    }
	    .confirm-dialog {
	      grid-template-rows: auto auto auto;
	      width: min(420px, 100%);
	      max-height: none;
	    }
	    .site-editor-head {
	      display: flex;
	      align-items: center;
	      justify-content: space-between;
	      gap: 12px;
	      padding: 12px 14px;
	      border-bottom: 1px solid var(--line);
	      background: var(--panel-soft);
	    }
	    .site-editor-title {
	      display: grid;
	      gap: 3px;
	      min-width: 0;
	    }
	    .site-editor-title strong {
	      color: var(--ink);
	      font-size: 15px;
	    }
	    .site-editor-user {
	      overflow: hidden;
	      text-overflow: ellipsis;
	      white-space: nowrap;
	    }
	    .site-editor-body {
	      overflow: auto;
	      padding: 14px;
	    }
	    .confirm-message {
	      margin: 0;
	      color: var(--ink);
	      line-height: 1.6;
	    }
	    .site-editor-body .site-grid {
	      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
	    }
	    .site-editor-actions {
	      display: flex;
	      justify-content: flex-end;
	      gap: 8px;
	      padding: 12px 14px;
	      border-top: 1px solid var(--line);
	      background: #fff;
	    }
	    .toast {
      position: fixed;
      right: 18px;
      bottom: 18px;
      max-width: min(420px, calc(100vw - 36px));
      background: #111827;
      color: #fff;
      padding: 10px 12px;
      border-radius: 8px;
      box-shadow: 0 10px 24px rgba(0, 0, 0, .18);
      opacity: 0;
      transform: translateY(8px);
      pointer-events: none;
      transition: .18s ease;
      z-index: 30;
    }
    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }
    @media (max-width: 980px) {
      header { align-items: flex-start; flex-direction: column; }
      .dashboard-titlebar {
        align-items: flex-start;
        flex-direction: column;
      }
      .home-actions { justify-content: flex-start; }
      .home-stat-grid { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
      .overview-grid,
      .home-lower-grid { grid-template-columns: 1fr; }
      .donut-layout { grid-template-columns: minmax(0, .8fr) minmax(0, 1fr); }
      .rooms-page-head {
        align-items: flex-start;
        flex-direction: column;
      }
      .rooms-actions { justify-content: flex-start; }
      .rooms-metric-grid { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
      .rooms-command-grid { grid-template-columns: 1fr; }
      .room-command-card .toolbar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .toolbar,
      .bulkbar,
      .room-filterbar { grid-template-columns: 1fr; }
      .anchor-grid { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
      .batch { grid-template-columns: 1fr; }
	      .user-toolbar { grid-template-columns: 1fr; }
      .room-list-summary { justify-self: start; white-space: normal; }
      .pager { justify-content: flex-start; flex-wrap: wrap; }
      .config-layout { grid-template-columns: 1fr; }
      .config-cards { grid-template-columns: 1fr; }
      .config-card.wide { grid-column: auto; }
      .config-card-body { grid-template-columns: 1fr; }
      .config-field.long { grid-column: auto; }
      .section-list { border-right: 0; border-bottom: 1px solid var(--line); }
      table { table-layout: auto; }
      th, td { min-width: 120px; }
      .table-wrap { overflow-x: auto; }
    }
    @media (max-width: 560px) {
      header {
        width: calc(100% - 16px);
        top: 6px;
      }
      main { padding: 12px 8px 24px; }
      .tabs { width: 100%; overflow-x: auto; }
      .tab { flex: 1 0 auto; }
      .home-shell { padding: 6px; }
      .dashboard-titlebar { gap: 10px; }
      .dashboard-subtitle {
        display: block;
        margin-left: 0;
        margin-top: 3px;
      }
      #dashboardCopy {
        white-space: normal;
      }
      .home-actions {
        width: 100%;
      }
      .home-actions button {
        flex: 1 1 auto;
      }
      .home-stat-grid { grid-template-columns: 1fr; }
      .rooms-workspace { padding: 6px; }
      .rooms-page-head { gap: 10px; }
      .rooms-actions {
        width: 100%;
      }
      .rooms-actions button {
        flex: 1 1 auto;
      }
      .rooms-metric-grid { grid-template-columns: 1fr; }
      .room-command-head {
        align-items: flex-start;
        flex-direction: column;
      }
      .room-command-body,
      .bulkbar,
      .room-filterbar {
        padding: 12px;
      }
      .room-command-card .toolbar { grid-template-columns: 1fr; }
      .room-command-card .toolbar .form-field:nth-child(5) { grid-column: auto; }
      .room-toggle-group {
        align-items: flex-start;
        flex-direction: column;
      }
      .overview-grid { padding: 0 8px 8px; }
      .donut-card { min-height: auto; }
      .donut-card-head {
        align-items: flex-start;
        flex-direction: column;
        padding: 10px 14px 0;
      }
	      .donut-layout {
	        grid-template-columns: 1fr;
	        padding: 12px 16px 18px;
	      }
      .mini-panel { height: auto; }
      .donut-chart { width: 148px; }
      .recent-card {
        grid-template-columns: 32px minmax(0, 1fr) 24px;
        gap: 5px;
        height: 44px;
        min-height: 44px;
        padding: 4px 6px;
      }
      .recent-avatar-wrap { width: 26px; height: 26px; font-size: 11px; }
      .recent-meta-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .recent-actions {
        position: relative;
        top: auto;
        left: auto;
        right: auto;
        grid-column: 3;
        justify-self: end;
        align-self: center;
        transform: none;
        opacity: 1;
        pointer-events: auto;
      }
      .recent-action-list {
        position: absolute;
        top: 50%;
        right: 24px;
        transform: translateY(-50%);
      }
      .anchor-grid { grid-template-columns: 1fr; }
	      .rank-row { grid-template-columns: minmax(132px, 1fr) minmax(72px, .7fr) 58px; }
      .trend-compact .trend-row { grid-template-columns: 42px minmax(0, 1fr); }
      .trend-compact .trend-value { grid-column: 1 / -1; max-width: none; }
      .topline { width: 100%; }
      #logoutButton { width: 100%; }
    }
    @media (max-width: 700px) {
      body {
        min-width: 320px;
        overflow-x: hidden;
      }
      input,
      select,
      textarea {
        font-size: 16px;
      }
      .room-table-wrap,
      #view-users .table-wrap {
        overflow: visible;
        border-top: 0;
        background: transparent;
      }
      .rooms-table,
      #view-users table,
      .rooms-table thead,
      #view-users table thead,
      .rooms-table tbody,
      #view-users table tbody {
        display: block;
        width: 100%;
      }
      .rooms-table thead,
      #view-users table thead {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
        white-space: nowrap;
      }
      .rooms-table tbody,
      #view-users table tbody {
        display: grid;
        gap: 10px;
        padding: 10px;
      }
      .rooms-table tbody tr,
      #view-users table tbody tr {
        display: grid;
        gap: 9px;
        padding: 10px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #fff;
        box-shadow: var(--shadow-soft);
      }
      .rooms-table tbody tr:hover td {
        background: transparent;
      }
      .rooms-table td,
      #view-users table td {
        display: grid;
        grid-template-columns: 78px minmax(0, 1fr);
        align-items: center;
        gap: 8px;
        min-width: 0;
        height: auto;
        padding: 0;
        border-bottom: 0;
        background: transparent;
      }
      .rooms-table td::before,
      #view-users table td::before {
        color: #64748b;
        content: "";
        font-size: 11px;
        font-weight: 800;
        line-height: 1.2;
      }
      .rooms-table td[colspan],
      #view-users table td[colspan] {
        display: block;
        padding: 14px;
        color: var(--muted);
        text-align: center;
      }
      .rooms-table td[colspan]::before,
      #view-users table td[colspan]::before {
        content: none;
      }
      .rooms-table td:nth-child(1)::before { content: "选择"; }
      .rooms-table td:nth-child(2)::before { content: "状态"; }
      .rooms-table td:nth-child(3)::before { content: "星级"; }
      .rooms-table td:nth-child(4)::before { content: "分组"; }
      .rooms-table td:nth-child(5)::before { content: "用户"; }
      .rooms-table td:nth-child(6)::before { content: "画质"; }
      .rooms-table td:nth-child(7)::before { content: "字幕"; }
      .rooms-table td:nth-child(8)::before { content: "烧录"; }
      .rooms-table td:nth-child(9)::before { content: "直播间 URL"; }
      .rooms-table td:nth-child(10)::before { content: "主播"; }
      .rooms-table td:nth-child(11)::before { content: "操作"; }
      #view-users table td:nth-child(1)::before { content: "用户名"; }
      #view-users table td:nth-child(2)::before { content: "启用"; }
      #view-users table td:nth-child(3)::before { content: "密码"; }
      #view-users table td:nth-child(4)::before { content: "备注"; }
      #view-users table td:nth-child(5)::before { content: "可录制平台"; }
      #view-users table td:nth-child(6)::before { content: "操作"; }
      .rooms-table td:first-child input,
      #view-users table input[type="checkbox"] {
        justify-self: end;
      }
      .rooms-table td:nth-child(9),
      .rooms-table td:nth-child(10),
      .rooms-table td:nth-child(11),
      #view-users table td:nth-child(5),
      #view-users table td:nth-child(6) {
        grid-template-columns: 1fr;
        align-items: stretch;
      }
      .rooms-table input:not([type="checkbox"]),
      .rooms-table select,
      #view-users table input:not([type="checkbox"]) {
        min-height: 40px;
      }
      .rooms-table .row-actions,
      #view-users table .row-actions {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        justify-content: stretch;
      }
      .rooms-table .row-actions button,
      #view-users table .row-actions button,
      .permission-summary button {
        width: 100%;
      }
      .permission-summary {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 560px) {
      header {
        gap: 8px;
        width: calc(100% - 12px);
        margin-top: 6px;
        padding: 8px;
        border-radius: 8px;
      }
      h1 {
        min-width: 0;
        overflow: hidden;
        font-size: 16px;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .topline {
        display: grid;
        grid-template-columns: 30px minmax(0, 1fr) auto;
        gap: 7px;
      }
      .topline #version {
        grid-column: 2 / -1;
        min-width: 0;
      }
      .topline #accountBadge {
        justify-self: end;
        max-width: 100%;
      }
      .tabs {
        gap: 4px;
        padding: 2px;
        scrollbar-width: none;
      }
      .tabs::-webkit-scrollbar {
        display: none;
      }
      .tab {
        min-height: 36px;
        padding: 6px 10px;
        font-size: 13px;
        text-align: center;
      }
      main {
        padding: 10px 6px 22px;
      }
      .login-screen {
        min-height: 100svh;
        padding: 14px;
      }
      .login-panel {
        padding: 18px;
      }
      .home-stat-grid,
      .rooms-metric-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }
      .home-stat-card,
      .rooms-metric-card {
        min-height: 80px;
        padding: 12px;
      }
      .home-stat-card strong,
      .rooms-metric-card strong {
        font-size: 24px;
      }
      .home-actions .dashboard-subtitle {
        flex: 1 0 100%;
      }
      .home-actions,
      .rooms-actions {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
      }
      .home-actions .status,
      .home-actions .dashboard-subtitle,
      .rooms-actions #refreshRooms {
        grid-column: 1 / -1;
      }
      .home-actions button,
      .rooms-actions button {
        width: 100%;
        min-width: 0;
      }
      .overview-band .band-head {
        align-items: stretch;
        flex-direction: column;
        gap: 8px;
      }
      .overview-head-main {
        align-items: flex-start;
        flex-direction: column;
        gap: 8px;
      }
      .range-tabs {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        width: 100%;
      }
      .range-tab {
        min-width: 0;
        padding: 4px 6px;
      }
      .summary-pills {
        width: 100%;
      }
      .band-head,
      .mini-head,
      .config-card-head,
      .site-editor-head {
        align-items: flex-start;
        flex-direction: column;
      }
      .band-head > button,
      .config-card-head button,
      .site-editor-head button {
        width: 100%;
      }
      .room-command-head .muted,
      .mini-head .muted {
        width: 100%;
      }
      .room-command-card,
      .room-list-card,
      .band,
      .home-shell,
      .rooms-workspace {
        box-shadow: none;
      }
      .room-toggle-group {
        align-items: center;
        flex-direction: row;
        gap: 8px 12px;
      }
      .check-field {
        min-height: 32px;
      }
      .batch textarea,
      textarea {
        min-height: 120px;
      }
      .pager {
        display: grid;
        grid-template-columns: 1fr 1fr;
      }
      .pager-info {
        grid-column: 1 / -1;
        grid-row: 1;
        width: 100%;
        min-width: 0;
      }
      .pager button {
        width: 100%;
      }
      .config-layout {
        min-height: 0;
      }
      .section-list {
        display: flex;
        gap: 6px;
        overflow-x: auto;
        padding: 8px;
        scrollbar-width: none;
      }
      .section-list::-webkit-scrollbar {
        display: none;
      }
      .section-btn {
        flex: 0 0 auto;
        width: auto;
        margin-bottom: 0;
      }
      .config-cards {
        padding: 8px;
      }
      .config-card-body {
        gap: 9px;
        padding: 10px;
      }
      .site-grid,
      .site-editor-body .site-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .site-editor-backdrop {
        align-items: flex-end;
        padding: 0;
      }
      .site-editor-dialog {
        width: 100%;
        max-height: 88svh;
        border-right: 0;
        border-bottom: 0;
        border-left: 0;
        border-radius: 8px 8px 0 0;
      }
      .site-editor-actions {
        display: grid;
        grid-template-columns: 1fr 1fr;
      }
      .site-editor-actions button {
        width: 100%;
      }
      .toast {
        right: 10px;
        bottom: 10px;
        left: 10px;
        max-width: none;
      }
    }
    @media (max-width: 380px) {
      .home-stat-grid,
      .rooms-metric-grid,
      .home-actions,
      .rooms-actions,
      .site-grid,
      .site-editor-body .site-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <section id="loginScreen" class="login-screen">
    <form id="loginForm" class="login-panel">
      <h2>🔐 登录控制台</h2>
      <p>输入 WebUI 用户名和密码，进入录播管理面板。</p>
      <div class="login-field">
        <label for="loginUsername">用户名</label>
        <input id="loginUsername" autocomplete="username">
      </div>
      <div class="login-field">
        <label for="loginPassword">密码</label>
        <input id="loginPassword" type="password" autocomplete="current-password">
      </div>
      <div id="loginError" class="login-error"></div>
      <div class="login-actions">
        <button id="loginButton" class="primary" type="submit">进入控制台</button>
      </div>
    </form>
  </section>
  <header>
    <div class="topline">
      <span class="brand-mark">DL</span>
      <h1>DouyinLiveRecorder</h1>
      <span id="version" class="muted"></span>
      <span id="accountBadge" class="pill"></span>
    </div>
    <nav class="tabs" aria-label="views">
      <button class="tab active" data-view="status">📊 状态</button>
      <button class="tab" data-view="rooms">🎥 直播间</button>
      <button class="tab" data-view="users" data-admin-only>👤 用户权限</button>
      <button class="tab" data-view="config" data-admin-only>⚙️ 配置</button>
    </nav>
    <button id="logoutButton">🚪 退出</button>
  </header>
  <main>
    <section id="view-status" class="view active">
      <div class="dashboard home-shell">
        <div class="dashboard-titlebar">
          <div>
            <h2>DouyinLiveRecorder <span id="serverTime" class="dashboard-subtitle"></span></h2>
            <span id="dashboardCopy" class="dashboard-subtitle">正在读取运行状态...</span>
          </div>
          <div class="home-actions">
            <span id="dashboardHealth" class="status waiting">待命</span>
            <span class="dashboard-subtitle">下次扫描 <strong id="metricDelay">0s</strong> · <span id="metricDelaySub">自动巡检</span></span>
            <button id="jumpRooms" class="primary" type="button">➕ 添加</button>
            <button id="enableAllRooms" type="button">全部启用</button>
            <button id="stopAllRooms" class="danger" type="button">全部停用</button>
            <button id="refreshDashboard" type="button">🔄 刷新</button>
          </div>
        </div>

        <div class="home-stat-grid">
          <div class="home-stat-card card-blue"><span>直播间</span><strong id="metricMonitoring">0</strong><em id="metricMonitoringSub">加载中</em></div>
          <div class="home-stat-card card-purple"><span>录制中</span><strong id="metricRecording">0</strong><em id="metricRecordingSub">暂无任务</em></div>
          <div class="home-stat-card card-orange"><span>累计录制</span><strong id="metricHistory">0</strong><em id="metricHistorySub">最近 30 天</em></div>
          <div class="home-stat-card card-indigo"><span>用户</span><strong id="metricUsers">1</strong><em id="metricUsersSub">当前账号</em></div>
        </div>

        <section class="band overview-band">
          <div class="band-head">
            <div class="overview-head-main">
              <h2 class="band-title">运行概览</h2>
              <div id="statusSummary" class="summary-pills"></div>
            </div>
            <div id="historyRangeTabs" class="range-tabs" role="group" aria-label="趋势范围">
              <button class="range-tab" type="button" data-history-range="7">7天</button>
              <button class="range-tab active" type="button" data-history-range="30">30天</button>
              <button class="range-tab" type="button" data-history-range="90">90天</button>
              <button class="range-tab" type="button" data-history-range="365">全年</button>
            </div>
          </div>
          <div class="overview-grid">
            <article class="donut-card">
              <div class="donut-card-head">
                <h3>直播间状态</h3>
                <span id="statusDonutHint">全部直播间</span>
              </div>
              <div class="donut-layout">
                <ul id="statusLegend" class="legend-list"></ul>
                <div id="statusDonut" class="donut-chart">
                  <div class="donut-hole"><strong id="statusDonutTotal">0</strong><span>总数</span></div>
                </div>
              </div>
            </article>
            <article class="donut-card">
              <div class="donut-card-head">
                <h3>平台/分组</h3>
                <span id="groupDonutHint">按配置分组</span>
              </div>
              <div class="donut-layout">
                <div id="groupDonut" class="donut-chart">
                  <div class="donut-hole"><strong id="groupDonutTotal">0</strong><span>分布</span></div>
                </div>
                <ul id="groupLegend" class="legend-list"></ul>
              </div>
            </article>
          </div>
        </section>

        <div class="home-lower-grid">
          <section class="mini-panel">
            <div class="mini-head">
              <h2 class="band-title">最近监控</h2>
              <span id="monitorHint" class="muted">按状态与录播时长排序</span>
            </div>
            <div id="recentMonitorPanel" class="recent-panel-body"></div>
          </section>
          <section class="mini-panel">
            <div class="mini-head">
              <h2 class="band-title">主播排行</h2>
              <span id="recordingTopHint" class="muted">最近 30 天</span>
            </div>
            <div id="recordingTopList" class="panel-body rank-list"></div>
          </section>
          <section class="mini-panel">
            <div class="mini-head">
              <h2 class="band-title">录制趋势</h2>
              <span id="historyRangeSummary" class="muted">最近 30 天</span>
            </div>
            <div id="historyTrendChart" class="panel-body trend-compact"></div>
          </section>
        </div>
      </div>
    </section>

    <section id="view-rooms" class="view">
      <div class="rooms-workspace">
        <div class="rooms-page-head">
          <div class="rooms-page-title">
            <h2>直播间管理</h2>
            <span>星级：★★★ 60秒 · ★★ 300秒 · ★ 600秒</span>
          </div>
          <div class="rooms-actions">
            <button id="importRooms" type="button">📥 导入</button>
            <button id="exportRooms" type="button">📤 导出</button>
            <input id="roomImportFile" type="file" accept=".ini,.txt,text/plain" hidden>
            <button id="refreshRooms" type="button">🔄 刷新</button>
          </div>
        </div>

        <div class="rooms-metric-grid">
          <div class="rooms-metric-card card-blue"><span>全部直播间</span><strong id="roomTotalMetric">0</strong><em id="roomTotalSub">暂无分组</em></div>
          <div class="rooms-metric-card card-green"><span>启用监控</span><strong id="roomEnabledMetric">0</strong><em id="roomEnabledSub">等待开播</em></div>
          <div class="rooms-metric-card card-orange"><span>录制中</span><strong id="roomRecordingMetric">0</strong><em id="roomRecordingSub">实时状态</em></div>
          <div class="rooms-metric-card card-purple"><span>已选择</span><strong id="roomSelectedMetric">0</strong><em id="roomSelectedSub">用于批量操作</em></div>
        </div>

        <div class="rooms-command-grid">
          <section class="room-command-card">
            <div class="room-command-head">
              <h3 class="room-command-title">快速添加</h3>
              <span class="muted">支持直播 URL 或手机分享文案</span>
            </div>
            <div class="room-command-body">
              <div class="toolbar">
                <label class="form-field"><span>画质</span><select id="addQuality"></select></label>
                <label class="form-field"><span>星级</span><select id="addPriority" title="★★★ 约60秒巡检；★★ 约300秒巡检；★ 约600秒巡检"></select></label>
                <label class="form-field"><span>分组</span><input id="addGroup" placeholder="默认按平台"></label>
                <label class="form-field" data-admin-only><span>用户</span><input id="addOwner" placeholder="留空为管理员"></label>
                <label class="form-field"><span>直播间</span><input id="addUrl" placeholder="直播间 URL 或手机端分享文案"></label>
                <label class="form-field"><span>主播</span><input id="addName" placeholder="主播名称"></label>
                <button id="addRoom" class="primary room-add-submit" type="button">➕ 添加</button>
                <div class="room-toggle-group">
                  <label class="check-field"><input id="addEnabled" type="checkbox" checked> 启用</label>
                  <label class="check-field"><input id="addSubtitle" type="checkbox"> 字幕</label>
                  <label class="check-field"><input id="addBurnSubtitle" type="checkbox"> 烧录</label>
                </div>
              </div>
            </div>
          </section>

          <section class="room-command-card">
            <div class="room-command-head">
              <h3 class="room-command-title">批量导入</h3>
              <span class="muted">一行一个直播间</span>
            </div>
            <div class="room-command-body">
              <div class="batch">
                <textarea id="batchText" placeholder="每行一个直播间，支持：URL、画质,URL、画质,URL,主播,分组: 抖音,用户: alice,★★★，也可直接粘贴手机端分享文案"></textarea>
                <button id="batchAdd" class="primary" type="button">批量添加</button>
              </div>
            </div>
          </section>
        </div>

        <section class="room-command-card">
          <div class="room-command-head">
            <h3 class="room-command-title">批量修改</h3>
            <span class="muted">先在列表中勾选直播间</span>
          </div>
          <div class="bulkbar">
            <label class="form-field"><span>状态</span><select id="bulkEnabled">
              <option value="">状态不变</option>
              <option value="true">启用</option>
              <option value="false">停用</option>
            </select></label>
            <label class="form-field"><span>画质</span><select id="bulkQuality"></select></label>
            <label class="form-field"><span>星级</span><select id="bulkPriority" title="批量设置星级：★★★ 约60秒；★★ 约300秒；★ 约600秒"></select></label>
            <label class="form-field"><span>分组</span><input id="bulkGroup" placeholder="留空不变"></label>
            <label class="form-field"><span>字幕</span><select id="bulkSubtitle">
              <option value="">字幕不变</option>
              <option value="true">录字幕</option>
              <option value="false">不录字幕</option>
            </select></label>
            <label class="form-field"><span>烧录</span><select id="bulkBurnSubtitle">
              <option value="">烧录不变</option>
              <option value="true">烧录字幕</option>
              <option value="false">不烧录</option>
            </select></label>
            <label class="form-field"><span>主播</span><input id="bulkName" placeholder="批量主播名称"></label>
            <button id="applyBulk" type="button">批量修改</button>
            <button id="deleteSelected" class="danger" type="button">删除所选</button>
          </div>
        </section>

        <section class="room-list-card">
          <div class="room-command-head">
            <h3 class="room-command-title">直播间列表</h3>
            <span id="roomListSummary" class="room-list-summary muted"></span>
          </div>
          <div class="room-filterbar">
            <input id="roomSearch" placeholder="搜索分组、主播或直播间 URL">
            <select id="roomGroupFilter">
              <option value="">全部分组</option>
            </select>
            <select id="roomStatusFilter">
              <option value="">全部状态</option>
              <option value="recording">录制中</option>
              <option value="waiting">等待</option>
              <option value="checking">检测</option>
              <option value="error">错误</option>
              <option value="disabled">停用</option>
              <option value="monitoring">监测</option>
            </select>
            <select id="roomPageSize">
              <option value="25">每页 25</option>
              <option value="50" selected>每页 50</option>
              <option value="100">每页 100</option>
              <option value="200">每页 200</option>
            </select>
            <button id="selectFilteredRooms" type="button">选择筛选</button>
            <button id="clearRoomSelection" type="button">清空选择</button>
          </div>
          <div class="table-wrap room-table-wrap">
            <table class="rooms-table">
              <thead>
                <tr>
                  <th style="width:48px"><input id="selectAllRooms" type="checkbox"></th>
                  <th style="width:84px">状态</th>
                  <th style="width:90px" title="★★★ 约60秒巡检；★★ 约300秒巡检；★ 约600秒巡检">星级</th>
                  <th style="width:120px">分组</th>
                  <th style="width:120px" data-admin-only>用户</th>
                  <th style="width:110px">画质</th>
                  <th style="width:72px">字幕</th>
                  <th style="width:72px">烧录</th>
                  <th>直播间 URL</th>
                  <th style="width:180px">主播</th>
                  <th style="width:150px">操作</th>
                </tr>
              </thead>
              <tbody id="roomRows"></tbody>
            </table>
          </div>
          <div class="pager">
            <button id="roomPrevPage" type="button">上一页</button>
            <span id="roomPageInfo" class="pager-info">第 1 / 1 页</span>
            <button id="roomNextPage" type="button">下一页</button>
          </div>
        </section>
      </div>
    </section>

    <section id="view-users" class="view">
      <div class="band">
        <div class="band-head">
          <h2 class="band-title">👤 用户权限</h2>
          <button id="refreshUsers" type="button">🔄 刷新</button>
        </div>
	        <div class="user-toolbar">
          <label class="form-field"><span>用户名</span><input id="userUsername" autocomplete="off"></label>
          <label class="form-field"><span>密码</span><input id="userPassword" type="password" autocomplete="new-password"></label>
          <label class="form-field"><span>备注</span><input id="userRemark"></label>
          <label class="check-field"><input id="userEnabled" type="checkbox" checked> 启用</label>
          <button id="saveUser" class="primary" type="button">保存用户</button>
          <button id="resetUserForm" type="button">清空</button>
        </div>
        <div class="permission-panel">
          <div id="userSiteGrid" class="site-grid"></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
	              <tr>
	                <th style="width:140px">用户名</th>
	                <th style="width:86px">启用</th>
	                <th style="width:160px">密码</th>
	                <th style="width:180px">备注</th>
	                <th style="width:240px">可录制平台</th>
	                <th style="width:150px">操作</th>
	              </tr>
	            </thead>
	            <tbody id="userRows"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section id="view-config" class="view">
      <div class="band">
        <div class="band-head">
          <h2 class="band-title">⚙️ 配置</h2>
          <label><input id="showSecrets" type="checkbox"> 显示敏感项</label>
        </div>
        <div class="config-layout">
          <aside id="sectionList" class="section-list"></aside>
          <section id="configCards" class="config-cards"></section>
        </div>
      </div>
	</section>
	  </main>
	  <div id="toast" class="toast"></div>
	  <div id="siteEditor" class="site-editor-backdrop" hidden>
	    <div class="site-editor-dialog" role="dialog" aria-modal="true" aria-labelledby="siteEditorTitle">
	      <div class="site-editor-head">
	        <div class="site-editor-title">
	          <strong id="siteEditorTitle">编辑录制权限</strong>
	          <span id="siteEditorUser" class="site-editor-user muted"></span>
	        </div>
	        <button id="closeSiteEditor" type="button">关闭</button>
	      </div>
	      <div class="site-editor-body">
	        <div id="managedSiteEditorGrid" class="site-grid"></div>
	      </div>
	      <div class="site-editor-actions">
	        <button id="cancelSiteEditor" type="button">取消</button>
	        <button id="saveSiteEditor" class="primary" type="button">保存权限</button>
	      </div>
	    </div>
	  </div>
	  <div id="confirmDialog" class="site-editor-backdrop" hidden>
	    <div class="site-editor-dialog confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirmTitle">
	      <div class="site-editor-head">
	        <div class="site-editor-title">
	          <strong id="confirmTitle">确认操作</strong>
	          <span id="confirmHint" class="site-editor-user muted"></span>
	        </div>
	        <button id="closeConfirm" type="button">关闭</button>
	      </div>
	      <div class="site-editor-body">
	        <p id="confirmMessage" class="confirm-message"></p>
	      </div>
	      <div class="site-editor-actions">
	        <button id="cancelConfirm" type="button">取消</button>
	        <button id="confirmAction" class="primary" type="button">确认</button>
	      </div>
	    </div>
	  </div>
	  <script>
    const qualities = ["原画", "蓝光", "超清", "高清", "标清", "流畅"];
    const state = {
	      rooms: [],
	      config: [],
	      users: [],
	      siteOptions: [],
	      currentUser: null,
      currentSection: "",
      currentView: "status",
      statusByUrl: new Map(),
      selectedRoomIds: new Set(),
      roomPage: 1,
      roomPageSize: 50,
      roomSearch: "",
      roomGroupFilter: "",
      roomStatusFilter: "",
      recordingRows: [],
      recordingSort: { key: "", direction: "asc" },
	      recordingByUrl: new Map(),
	      siteEditorUsername: "",
	      delayDefault: 0,
	      monitoringCount: 0,
	      checkingCount: 0,
	      nextScanAtMs: 0,
	      history: {},
	      historyRange: "30",
	      monitorRows: [],
	      monitorPage: 1,
	      monitorPageSize: 10
	    };
    let pendingConfirmResolve = null;
    let statusRequestInFlight = false;
    let lastStatusOkAt = 0;
    const STATUS_REFRESH_MS = 5000;
    const STATUS_REQUEST_TIMEOUT_MS = 12000;
    const API_REQUEST_TIMEOUT_MS = 15000;

    function headers() {
      return { "Content-Type": "application/json" };
    }
    function isAdmin() {
      return Boolean(state.currentUser && state.currentUser.role === "admin");
    }
    function renderUserMetric() {
      const managedCount = Array.isArray(state.users) ? state.users.length : 0;
      const total = isAdmin() ? managedCount + 1 : (state.currentUser ? 1 : 0);
      setText("metricUsers", total || 0);
      setText("metricUsersSub", isAdmin() ? `管理员 + ${managedCount} 个用户` : (state.currentUser?.username || "当前账号"));
    }
    function setCurrentUser(user) {
      state.currentUser = user || null;
      if (user && Array.isArray(user.site_options)) {
        state.siteOptions = user.site_options;
      }
      document.body.classList.toggle("admin", isAdmin());
      const badge = document.getElementById("accountBadge");
      if (badge) {
        badge.textContent = user ? `${user.username || "未命名"} · ${isAdmin() ? "管理员" : "用户"}` : "";
      }
      if (!isAdmin() && ["config", "users"].includes(state.currentView)) {
        openView("status");
      }
      renderUserMetric();
    }
    async function api(path, options = {}) {
      const { timeoutMs = API_REQUEST_TIMEOUT_MS, ...fetchOptions } = options;
      const controller = timeoutMs > 0 && typeof AbortController !== "undefined" && !fetchOptions.signal
        ? new AbortController()
        : null;
      const timeoutId = controller
        ? setTimeout(() => controller.abort(), timeoutMs)
        : null;
      try {
        const response = await fetch(path, {
          ...fetchOptions,
          credentials: "same-origin",
          signal: fetchOptions.signal || controller?.signal,
          headers: { ...headers(), ...(fetchOptions.headers || {}) }
        });
        if (response.status === 401) {
          showLogin();
          throw new Error("请先登录");
        }
        const payload = await response.json();
        if (!payload.ok) throw new Error(payload.message || "请求失败");
        return payload;
      } catch (error) {
        if (error && error.name === "AbortError") {
          throw new Error("请求超时，请稍后重试");
        }
        throw error;
      } finally {
        if (timeoutId) clearTimeout(timeoutId);
      }
    }
    function showLogin(message = "") {
      setCurrentUser(null);
      document.body.classList.remove("authenticated");
      document.getElementById("loginError").textContent = message;
      setTimeout(() => {
        const usernameInput = document.getElementById("loginUsername");
        const passwordInput = document.getElementById("loginPassword");
        (usernameInput.value.trim() ? passwordInput : usernameInput).focus();
      }, 0);
    }
    function showApp() {
      document.body.classList.add("authenticated");
      document.getElementById("loginError").textContent = "";
    }
    async function checkAuth() {
      try {
        const response = await fetch("/api/auth", { credentials: "same-origin" });
        const payload = await response.json();
        if (payload.authenticated) {
          setCurrentUser(payload.user);
          showApp();
          const tasks = [loadStatus(), loadRooms().catch(() => {})];
          if (isAdmin()) {
            tasks.push(loadConfig().catch(() => {}), loadUsers().catch(() => {}));
          }
          await Promise.all(tasks);
        } else {
          showLogin();
        }
      } catch (error) {
        showLogin("无法连接 WebUI 服务");
      }
    }
    async function login(username, password) {
      const response = await fetch("/api/login", {
        method: "POST",
        credentials: "same-origin",
        headers: headers(),
        body: JSON.stringify({ username, password })
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "登录失败");
      }
      setCurrentUser(payload.user);
      showApp();
      const tasks = [loadStatus(), loadRooms()];
      if (isAdmin()) {
        tasks.push(loadConfig(), loadUsers());
      }
      await Promise.all(tasks);
    }
    async function logout() {
      await fetch("/api/logout", { method: "POST", credentials: "same-origin", headers: headers(), body: "{}" });
      showLogin();
    }
    function toast(message) {
      const box = document.getElementById("toast");
      box.textContent = message;
      box.classList.add("show");
      clearTimeout(toast.timer);
      toast.timer = setTimeout(() => box.classList.remove("show"), 2200);
    }
    function closeConfirmDialog(confirmed = false) {
      const dialog = document.getElementById("confirmDialog");
      if (dialog) dialog.hidden = true;
      if (pendingConfirmResolve) {
        pendingConfirmResolve(Boolean(confirmed));
        pendingConfirmResolve = null;
      }
    }
    function confirmDialog({ title = "确认操作", hint = "", message = "", confirmText = "确认", danger = false } = {}) {
      if (pendingConfirmResolve) closeConfirmDialog(false);
      const dialog = document.getElementById("confirmDialog");
      const actionButton = document.getElementById("confirmAction");
      setText("confirmTitle", title);
      setText("confirmHint", hint);
      setText("confirmMessage", message);
      actionButton.textContent = confirmText;
      actionButton.classList.toggle("danger", Boolean(danger));
      actionButton.classList.toggle("primary", !danger);
      dialog.hidden = false;
      requestAnimationFrame(() => actionButton.focus());
      return new Promise(resolve => {
        pendingConfirmResolve = resolve;
      });
    }
    function optionList(selected = "", includeKeep = false) {
      const prefix = includeKeep ? `<option value="">画质不变</option>` : "";
      return prefix + qualities.map(q => `<option value="${q}" ${q === selected ? "selected" : ""}>${q}</option>`).join("");
    }
    function priorityOptions(selected = "", includeKeep = false) {
      const normalized = String(selected || "");
      const options = [
        ["★★★", "★★★ 三星"],
        ["★★", "★★ 二星"],
        ["★", "★ 一星"],
        ["__clear__", "无星级"]
      ];
      const prefix = includeKeep ? `<option value="">星级不变</option>` : "";
      return prefix + options.map(([value, label]) => `
        <option value="${value}" ${value === normalized ? "selected" : ""}>${label}</option>
      `).join("");
    }
    function statusLabel(value) {
      const map = {
        recording: "录制中",
        waiting: "等待",
        checking: "检测",
        disabled: "停用",
        error: "错误",
        finished: "完成",
        stopped: "停止",
        queued: "排队",
        live: "直播中"
      };
      return map[value] || "监测";
    }
    function statusClass(value) {
      if (["recording", "live"].includes(value)) return "recording";
      if (["waiting", "queued", "finished"].includes(value)) return "waiting";
      if (value === "error") return "error";
      if (value === "checking") return "checking";
      if (["disabled", "stopped"].includes(value)) return "disabled";
      return "";
    }
    function statusPriority(value) {
      if (["recording", "live"].includes(value)) return 0;
      if (value === "error") return 1;
      if (value === "checking") return 2;
      if (["waiting", "queued"].includes(value)) return 3;
      if (["disabled", "stopped", "finished"].includes(value)) return 4;
      return 5;
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    }
	    function setText(id, value) {
	      const element = document.getElementById(id);
	      if (element) element.textContent = value;
	    }
	    function capturePageScroll() {
	      const root = document.scrollingElement || document.documentElement;
	      return { left: root.scrollLeft, top: root.scrollTop };
	    }
	    function restorePageScroll(snapshot) {
	      if (!snapshot) return;
	      requestAnimationFrame(() => {
	        const root = document.scrollingElement || document.documentElement;
	        const maxTop = Math.max(0, root.scrollHeight - window.innerHeight);
	        root.scrollTo({ left: snapshot.left, top: Math.min(snapshot.top, maxTop), behavior: "auto" });
	      });
	    }
    function parseShareText(text) {
      const urlMatch = String(text || "").match(/https?:\/\/[^\s，,。；;）)】》>"']+/);
      const namePatterns = [
        /【([^】]{1,80})】\s*正在直播/,
        /@([^，,。；;\s]{1,80})\s*正在直播/,
        /主播[:：]\s*([^，,。；;\s]{1,80})/
      ];
      let name = "";
      for (const pattern of namePatterns) {
        const match = String(text || "").match(pattern);
        if (match) {
          name = match[1].trim();
          break;
        }
      }
      return {
        url: urlMatch ? urlMatch[0].replace(/[.。!！?？;；:：]+$/, "") : "",
        name
      };
    }
    let shareResolveSeq = 0;
    async function fillShareText() {
      const urlInput = document.getElementById("addUrl");
      const nameInput = document.getElementById("addName");
      const groupInput = document.getElementById("addGroup");
      const qualityInput = document.getElementById("addQuality");
      const rawText = urlInput.value;
      const parsed = parseShareText(rawText);
      if (!parsed.url) return;
      const seq = ++shareResolveSeq;
      if (parsed.name && !nameInput.value.trim()) {
        nameInput.value = parsed.name;
      }
      try {
        const preview = await api("/api/rooms/preview", { method: "POST", body: JSON.stringify({
          quality: qualityInput.value,
          url: rawText,
          name: nameInput.value.trim(),
          group: groupInput.value.trim(),
          owner: isAdmin() ? document.getElementById("addOwner").value.trim() : ""
        }) });
        if (seq !== shareResolveSeq) return;
        if (preview.data && preview.data.url) {
          urlInput.value = preview.data.url;
        }
        if (preview.data && preview.data.name && !nameInput.value.trim()) {
          nameInput.value = preview.data.name;
        }
        if (preview.data && preview.data.group && !groupInput.value.trim()) {
          groupInput.value = preview.data.group;
        }
      } catch (error) {
        if (seq === shareResolveSeq && parsed.url !== urlInput.value.trim()) {
          urlInput.value = parsed.url;
        }
      }
    }
    function fmtDuration(seconds) {
      seconds = Math.max(0, Number(seconds || 0));
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      const s = Math.floor(seconds % 60);
      return [h, m, s].map(v => String(v).padStart(2, "0")).join(":");
    }
    function metricNumber(value) {
      const number = Number(value);
      return Number.isFinite(number) ? number : null;
    }
    function fmtPercent(value) {
      const number = metricNumber(value);
      return number === null ? "-" : `${Math.round(number)}%`;
    }
    function fmtGb(value) {
      const number = metricNumber(value);
      return number === null ? "-" : `${number.toFixed(number >= 10 ? 0 : 1)}GB`;
    }
    function resourcePill(label, metric, title) {
      const percent = metricNumber(metric?.percent);
      const level = percent === null ? "" : percent >= 90 ? "bad" : percent >= 75 ? "warn" : "";
      return `<span class="pill resource ${level}" title="${escapeHtml(title || "")}">${label} ${fmtPercent(percent)}</span>`;
    }
    function renderNextScanMetric() {
      const remaining = state.nextScanAtMs
        ? Math.max(0, Math.ceil((state.nextScanAtMs - Date.now()) / 1000))
        : 0;
      const value = state.monitoringCount
        ? (remaining > 0 ? `${remaining}s` : state.checkingCount ? "检测中" : "0s")
        : "0s";
      const sub = state.monitoringCount
        ? (state.delayDefault ? `间隔 ${state.delayDefault}s` : "连续检查")
        : "暂无巡检";
      setText("metricDelay", value);
      setText("metricDelaySub", sub);
    }
    function formatCheckTime(value) {
      const text = String(value || "");
      const match = text.match(/T(\d{2}:\d{2}:\d{2})/);
      return match ? match[1] : text.replace("T", " ");
    }
    function formatStartTime(value) {
      const text = formatCheckTime(value);
      return text || "-";
    }
    function roomDisplayName(row) {
      return row.anchor_name || row.configured_name || row.record_name || row.url || "未命名";
    }
    function roomRecordingStats(row) {
      const recording = state.recordingByUrl.get(row.url) || {};
      const startedAt = recording.started_at || row.started_at || "";
      const elapsed = Number(recording.elapsed_seconds ?? row.elapsed_seconds ?? 0);
      const active = ["recording", "live"].includes(row.status) || Boolean(recording.started_at);
      return {
        startedAt,
        elapsedSeconds: active && elapsed > 0 ? elapsed : 0,
      };
    }
    function roomConfigByUrl(url) {
      return state.rooms.find(room => room.url && room.url === url) || null;
    }
    function monitorRoomId(row) {
      const configured = roomConfigByUrl(row.url);
      return Number(row.id || configured?.id || 0);
    }
    function monitorRoomEnabled(row) {
      if (typeof row.enabled === "boolean") return row.enabled;
      const configured = roomConfigByUrl(row.url);
      if (configured && typeof configured.enabled === "boolean") return configured.enabled;
      return row.status !== "disabled";
    }
    function monitorRoomActionButtons(row) {
      const roomId = monitorRoomId(row);
      const name = roomDisplayName(row);
      const hasRoom = roomId > 0;
      const enabled = monitorRoomEnabled(row);
      const commonAttrs = `data-room-id="${hasRoom ? roomId : ""}" data-room-name="${escapeHtml(name)}" data-room-url="${escapeHtml(row.url || "")}"`;
      return `
        <button type="button" class="monitor-room-action recent-room-action" data-monitor-action="disable" ${commonAttrs} ${hasRoom && enabled ? "" : "disabled"} title="${enabled ? "停用直播间" : "直播间已停用"}">停用</button>
        <button type="button" class="monitor-room-action recent-room-action danger" data-monitor-action="disable-delete" ${commonAttrs} ${hasRoom ? "" : "disabled"} title="停用并删除直播间">停删</button>
      `;
    }
    function recentMonitorActionsMarkup(row) {
      return `
        <div class="recent-actions">
          <button type="button" class="recent-action-trigger" title="直播间操作" aria-label="直播间操作">...</button>
          <div class="recent-action-list">
            ${monitorRoomActionButtons(row)}
          </div>
        </div>
      `;
    }
    const recordingGreen = "#00c853";
    const dashboardPalette = ["#7369f3", "#9b64f0", "#ef5d93", "#48c3aa", "#ff9d4d", "#5b93f3", "#f2c94c", "#8a98aa"];
    function donutGradient(items, total) {
      if (!total) return "#edf1f7";
      let cursor = 0;
      const stops = items.map(item => {
        const start = cursor;
        cursor += (Number(item.value || 0) / total) * 360;
        return `${item.color} ${start.toFixed(2)}deg ${cursor.toFixed(2)}deg`;
      });
      return `conic-gradient(${stops.join(", ")})`;
    }
    function renderDonutChart({ chartId, legendId, totalId, hintId, hint, items, emptyLabel = "暂无数据" }) {
      const chart = document.getElementById(chartId);
      const legend = document.getElementById(legendId);
      const totalEl = document.getElementById(totalId);
      const hintEl = document.getElementById(hintId);
      if (!chart || !legend) return;
      const visibleItems = items.filter(item => Number(item.value || 0) > 0);
      const total = visibleItems.reduce((sum, item) => sum + Number(item.value || 0), 0);
      chart.style.setProperty("--donut-bg", donutGradient(visibleItems, total));
      if (totalEl) totalEl.textContent = total;
      if (hintEl && hint) hintEl.textContent = hint;
      legend.innerHTML = visibleItems.length ? visibleItems.map(item => `
        <li class="legend-item" style="--dot-color:${item.color}">
          <span class="legend-dot"></span>
          <span class="legend-name" title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</span>
          <span class="legend-value">${Number(item.value || 0)}</span>
        </li>
      `).join("") : `
        <li class="legend-item" style="--dot-color:#cbd5e1">
          <span class="legend-dot"></span>
          <span class="legend-name">${emptyLabel}</span>
          <span class="legend-value">0</span>
        </li>
      `;
    }
    function topCountItems(counts, limit = 8) {
      const rows = Array.from(counts.entries())
        .map(([label, value], index) => ({ label, value, color: dashboardPalette[index % dashboardPalette.length] }))
        .sort((left, right) => Number(right.value || 0) - Number(left.value || 0));
      if (rows.length <= limit) return rows;
      const head = rows.slice(0, limit - 1);
      const other = rows.slice(limit - 1).reduce((sum, item) => sum + Number(item.value || 0), 0);
      return [...head, { label: "其他", value: other, color: dashboardPalette[(limit - 1) % dashboardPalette.length] }];
    }
    function renderHomeDistributions(rows, statusCounts) {
      const statusItems = [
        { label: "录制中", value: statusCounts.recording, color: recordingGreen },
        { label: "等待", value: statusCounts.waiting, color: dashboardPalette[1] },
        { label: "检测", value: statusCounts.checking, color: dashboardPalette[3] },
        { label: "停用", value: statusCounts.disabled, color: dashboardPalette[5] },
        { label: "异常", value: statusCounts.error, color: dashboardPalette[2] },
        { label: "其他", value: statusCounts.other, color: dashboardPalette[7] }
      ];
      renderDonutChart({
        chartId: "statusDonut",
        legendId: "statusLegend",
        totalId: "statusDonutTotal",
        hintId: "statusDonutHint",
        hint: `${rows.length} 个直播间`,
        items: statusItems
      });
      const groupCounts = new Map();
      rows.forEach(row => {
        const group = row.group || row.configured_group || row.platform || "其他";
        groupCounts.set(group, (groupCounts.get(group) || 0) + 1);
      });
      renderDonutChart({
        chartId: "groupDonut",
        legendId: "groupLegend",
        totalId: "groupDonutTotal",
        hintId: "groupDonutHint",
        hint: `${groupCounts.size || 0} 个分组`,
        items: topCountItems(groupCounts, 8)
      });
    }
    function historyRangeLabel(range) {
      return range === "365" ? "全年" : `${range}天`;
    }
	    function fmtCompactDuration(seconds) {
	      seconds = Math.max(0, Number(seconds || 0));
	      if (seconds < 60) return `${Math.floor(seconds)}秒`;
	      if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`;
	      const hours = seconds / 3600;
	      return `${hours >= 10 ? hours.toFixed(0) : hours.toFixed(1)}小时`;
	    }
	    function trendHeatStyle(seconds, maxSeconds) {
	      const ratio = Math.max(0, Math.min(1, Number(seconds || 0) / Math.max(1, Number(maxSeconds || 1))));
	      if (ratio < 0.25) {
	        return "--trend-fill:linear-gradient(90deg,#dbe8ff,#a9c6ff);--trend-glow:rgba(169,198,255,.10)";
	      }
	      if (ratio < 0.5) {
	        return "--trend-fill:linear-gradient(90deg,#9fb9ff,#58c3d5);--trend-glow:rgba(88,195,213,.12)";
	      }
	      if (ratio < 0.75) {
	        return "--trend-fill:linear-gradient(90deg,#6dd7b2,#ffd166);--trend-glow:rgba(255,209,102,.16)";
	      }
	      if (ratio < 0.9) {
	        return "--trend-fill:linear-gradient(90deg,#ffd166,#ff8a3d);--trend-glow:rgba(255,138,61,.20)";
	      }
	      return "--trend-fill:linear-gradient(90deg,#ffb13b,#ff3b30);--trend-glow:rgba(255,59,48,.24)";
	    }
    function updateHistoryRangeTabs() {
      document.querySelectorAll("[data-history-range]").forEach(button => {
        button.classList.toggle("active", button.dataset.historyRange === state.historyRange);
      });
    }
    function renderHistoryTrend(history = state.history) {
      updateHistoryRangeTabs();
      const ranges = history?.ranges || {};
      const rangeData = ranges[state.historyRange] || ranges["30"] || ranges["7"] || { days: [] };
      const days = Array.isArray(rangeData.days) ? rangeData.days : [];
      const rangeLabel = rangeData.label || historyRangeLabel(state.historyRange);
      const recordingsTotal = Number(rangeData.recordings || 0);
      const durationTotal = Number(rangeData.duration_seconds || 0);
      setText("metricHistory", recordingsTotal);
      setText("metricHistorySub", `${rangeLabel} / ${fmtCompactDuration(durationTotal)}`);
      setText(
        "historyRangeSummary",
        `${rangeLabel} ${recordingsTotal} 次 / ${fmtCompactDuration(durationTotal)}`
      );
      setText("recordingTopHint", rangeLabel);

      const container = document.getElementById("historyTrendChart");
      if (!container) return;
      const activeDays = days
        .filter(day => Number(day.recordings || 0) || Number(day.duration_seconds || 0))
        .slice(-8)
        .reverse();
      const maxDuration = Math.max(1, ...activeDays.map(day => Number(day.duration_seconds || 0)));
      const avgDuration = days.length ? Math.round(durationTotal / days.length) : 0;
      const recentRows = activeDays.length ? activeDays.map(day => {
	        const recordings = Number(day.recordings || 0);
	        const durationSeconds = Number(day.duration_seconds || 0);
	        const width = Math.max(3, Math.round((durationSeconds / maxDuration) * 100));
	        const heatStyle = trendHeatStyle(durationSeconds, maxDuration);
	        return `
	          <div class="trend-row" title="${escapeHtml(day.date || "")}">
	            <div class="trend-date">${escapeHtml(day.label || day.date || "")}</div>
	            <div class="trend-track"><div class="trend-fill" style="width:${width}%;${heatStyle}"></div></div>
	            <div class="trend-value">${recordings} 次 / ${fmtCompactDuration(durationSeconds)}</div>
	          </div>
	        `;
      }).join("") : `<div class="muted">所选范围内暂无录制记录。</div>`;
      container.innerHTML = `
        <div class="trend-summary">
          <div class="trend-summary-item"><span>录制次数</span><strong>${recordingsTotal}</strong></div>
          <div class="trend-summary-item"><span>总录播时长</span><strong>${fmtCompactDuration(durationTotal)}</strong></div>
          <div class="trend-summary-item"><span>日均时长</span><strong>${fmtCompactDuration(avgDuration)}</strong></div>
        </div>
        <div class="trend-list">${recentRows}</div>
      `;
      renderRecordingTop(rangeData.anchor_top || []);
    }
	    function renderRecordingTop(rows) {
	      const container = document.getElementById("recordingTopList");
	      if (!container) return;
      const sortedRows = [...rows]
        .sort((left, right) => {
          const rightSeconds = Number(right.duration_seconds ?? right.elapsed_seconds ?? 0);
          const leftSeconds = Number(left.duration_seconds ?? left.elapsed_seconds ?? 0);
          if (rightSeconds !== leftSeconds) return rightSeconds - leftSeconds;
          return Number(right.recordings || 0) - Number(left.recordings || 0);
        })
        .slice(0, 10);
      const maxSeconds = Math.max(1, ...sortedRows.map(row => Number(row.duration_seconds ?? row.elapsed_seconds ?? 0)));
      container.innerHTML = sortedRows.length ? sortedRows.map(row => {
        const seconds = Number(row.duration_seconds ?? row.elapsed_seconds ?? 0);
	        const width = Math.max(1, Math.round((seconds / maxSeconds) * 100));
	        const name = row.name || row.anchor_name || row.record_name || "未命名";
	        const recordings = Number(row.recordings || 0);
	        const avatarUrl = rankAvatarUrl(row, name);
	        const avatarLabel = String(name || "主").trim().slice(0, 1) || "主";
	        return `
	          <div class="rank-row">
	            <div class="rank-profile">
	              <span class="rank-avatar fallback ${avatarUrl ? "hidden" : ""}">${escapeHtml(avatarLabel)}</span>
	              ${avatarUrl ? `<img class="rank-avatar" src="${escapeHtml(avatarUrl)}" alt="" loading="lazy" onerror="this.previousElementSibling.classList.remove('hidden');this.remove()">` : ""}
	              <div class="rank-name" title="${escapeHtml(name)}">
	                ${escapeHtml(name)}
	                <span class="rank-detail">${recordings ? `${recordings} 次录制` : "正在录制"}</span>
	              </div>
	            </div>
	            <div class="rank-track"><div class="rank-fill" style="width:${width}%"></div></div>
	            <div class="rank-value">${fmtCompactDuration(seconds)}</div>
	          </div>
	        `;
	      }).join("") : `<div class="muted">所选范围内暂无录制记录</div>`;
	    }
	    function rankNameKey(value) {
	      return String(value || "")
	        .replace(/^序号\s*\d+\s*/, "")
	        .trim()
	        .toLowerCase();
	    }
	    function rankAvatarUrl(row, name) {
	      if (row.avatar_url) return row.avatar_url;
	      const byUrl = row.url ? (state.statusByUrl.get(row.url) || state.recordingByUrl.get(row.url) || {}) : {};
	      if (byUrl.avatar_url) return byUrl.avatar_url;
	      const target = rankNameKey(name);
	      if (!target) return "";
	      const candidates = [
	        ...Array.from(state.statusByUrl.values()),
	        ...Array.from(state.recordingByUrl.values())
	      ];
	      const match = candidates.find(item => [
	        item.anchor_name,
	        item.configured_name,
	        item.record_name,
	        item.name
	      ].some(value => rankNameKey(value) === target));
	      return match?.avatar_url || "";
	    }
    function renderAnchorOverview(rows) {
      const container = document.getElementById("anchorOverviewGrid");
      const hint = document.getElementById("anchorOverviewHint");
      if (!container) return;
      const sortedRows = [...rows].sort((left, right) => {
        const priority = statusPriority(left.status) - statusPriority(right.status);
        if (priority) return priority;
        const rightStats = roomRecordingStats(right);
        const leftStats = roomRecordingStats(left);
        if (rightStats.elapsedSeconds !== leftStats.elapsedSeconds) {
          return rightStats.elapsedSeconds - leftStats.elapsedSeconds;
        }
        return roomDisplayName(left).localeCompare(roomDisplayName(right), "zh-Hans-CN", { numeric: true });
      });
      const visibleRows = sortedRows.slice(0, 20);
      if (hint) hint.textContent = rows.length > visibleRows.length ? `显示 ${visibleRows.length} / ${rows.length}` : "按状态与录播时长排序";
      container.innerHTML = visibleRows.length ? visibleRows.map((row, index) => {
        const stats = roomRecordingStats(row);
        return `
          <article class="anchor-card">
            <div class="anchor-card-head">
              <span class="anchor-card-name" title="${escapeHtml(roomDisplayName(row))}">${index + 1}. ${escapeHtml(roomDisplayName(row))}</span>
              <span class="status ${statusClass(row.status)}">${statusLabel(row.status)}</span>
            </div>
            <div class="anchor-card-meta">
              <span>${escapeHtml(row.quality || "")}</span>
              <span>${escapeHtml(formatStartTime(stats.startedAt))}</span>
            </div>
            <div class="anchor-card-meta">
              <span>录播时长</span>
              <span class="metric-chip">${stats.elapsedSeconds ? fmtDuration(stats.elapsedSeconds) : "-"}</span>
            </div>
          </article>
        `;
      }).join("") : `<div class="muted">暂无关注主播</div>`;
    }
    function recordingSortValue(row, key) {
      if (key === "elapsed_seconds") return Number(row.elapsed_seconds || 0);
      if (key === "quality") {
        const index = qualities.indexOf(row.quality || "");
        return index >= 0 ? index : qualities.length;
      }
      return String(row[key] || "").toLowerCase();
    }
    function sortedRecordingRows(rows) {
      const { key, direction } = state.recordingSort;
      if (!key) return [...rows];
      const order = direction === "desc" ? -1 : 1;
      return [...rows].sort((left, right) => {
        const leftValue = recordingSortValue(left, key);
        const rightValue = recordingSortValue(right, key);
        let result = 0;
        if (typeof leftValue === "number" && typeof rightValue === "number") {
          result = leftValue - rightValue;
        } else {
          result = String(leftValue).localeCompare(String(rightValue), "zh-Hans-CN", { numeric: true });
        }
        if (!result) {
          result = String(left.name || "").localeCompare(String(right.name || ""), "zh-Hans-CN", { numeric: true });
        }
        return result * order;
      });
    }
    function updateRecordingSortHeaders() {
      document.querySelectorAll("[data-recording-sort]").forEach(button => {
        const key = button.dataset.recordingSort;
        const active = state.recordingSort.key === key;
        const indicator = document.querySelector(`[data-sort-indicator="${key}"]`);
        button.classList.toggle("active", active);
        button.setAttribute("aria-sort", active ? (state.recordingSort.direction === "asc" ? "ascending" : "descending") : "none");
        if (indicator) indicator.textContent = active ? (state.recordingSort.direction === "asc" ? "▲" : "▼") : "↕";
      });
    }
    function setRecordingSort(key) {
      if (state.recordingSort.key === key) {
        state.recordingSort.direction = state.recordingSort.direction === "asc" ? "desc" : "asc";
      } else {
        state.recordingSort = { key, direction: key === "elapsed_seconds" ? "desc" : "asc" };
      }
      renderRecording(state.recordingRows);
    }
    function renderSelects() {
      document.getElementById("addQuality").innerHTML = optionList("原画");
      document.getElementById("addPriority").innerHTML = priorityOptions("★★");
      document.getElementById("bulkQuality").innerHTML = optionList("", true);
      document.getElementById("bulkPriority").innerHTML = priorityOptions("", true);
    }
	    async function loadStatus({ quiet = true } = {}) {
	      if (statusRequestInFlight) return;
	      statusRequestInFlight = true;
	      try {
	        const { data } = await api("/api/status", { timeoutMs: STATUS_REQUEST_TIMEOUT_MS });
	        lastStatusOkAt = Date.now();
	        if (data.user) setCurrentUser(data.user);
        const rooms = data.rooms || [];
        const recording = data.recording || [];
        const disabledUrls = new Set(data.disabled_urls || []);
        const monitoringCount = Number(data.monitoring ?? rooms.filter(item => item.status !== "disabled").length);
        const recordingCount = Number(data.recording_count ?? recording.length);
        const roomErrorCount = Number(data.room_error_count ?? rooms.filter(
          item => item.status === "error" && !disabledUrls.has(item.url)
        ).length);
        const instantErrorCount = Number(data.instant_error_count ?? data.error_count ?? 0);
        const recordingRoomCount = rooms.filter(item => ["recording", "live"].includes(item.status) && !disabledUrls.has(item.url)).length;
        const recordingDistributionCount = recordingRoomCount || Math.min(recordingCount, rooms.length);
        const disabledCount = rooms.filter(item => ["disabled", "stopped"].includes(item.status) || disabledUrls.has(item.url)).length;
        const waitingCount = rooms.filter(item => ["waiting", "queued", "finished"].includes(item.status) && !disabledUrls.has(item.url)).length;
        const checkingCount = rooms.filter(item => item.status === "checking").length;
        const otherStatusCount = Math.max(0, rooms.length - recordingDistributionCount - disabledCount - waitingCount - checkingCount - roomErrorCount);
        const totalRecordingSeconds = recording.reduce((total, item) => total + Number(item.elapsed_seconds || 0), 0);
	        const delay = Number(data.delay_default ?? 0);
	        const ringBase = Math.max(monitoringCount, recordingCount, 1);
	        const ringDeg = Math.min(360, Math.round((recordingCount / ringBase) * 360));
	        const scrollSnapshot = capturePageScroll();

        setText("version", data.version || "");
        setText("serverTime", data.server_time || "");
        setText("metricMonitoring", monitoringCount);
        setText("metricRecording", recordingCount);
        setText("metricThreads", data.max_request ?? 0);
        setText("metricErrors", instantErrorCount);
        setText("meterRecording", recordingCount);
        setText("metricMonitoringSub", disabledCount ? `${disabledCount} 个已停用` : "全部纳入巡检");
        setText("metricRecordingSub", recordingCount ? "任务正在写入" : "暂无任务");
        setText("metricThreadsSub", `最大 ${data.max_request ?? 0} 并发`);
        setText("metricErrorsSub", instantErrorCount ? `本轮 ${instantErrorCount} 次` : "稳定运行");
        setText("dashboardCopy", recordingCount
          ? `正在录制 ${recordingCount} 个直播，另有 ${Math.max(0, monitoringCount - recordingCount)} 个房间继续巡检。`
          : monitoringCount ? `当前监控 ${monitoringCount} 个直播间，等待开播后自动录制。` : "还没有启用的直播间，先添加一个开始监控。");

        const health = document.getElementById("dashboardHealth");
        if (health) {
          const healthClass = roomErrorCount ? "error" : recordingCount ? "recording" : checkingCount ? "checking" : "waiting";
          health.className = `status ${healthClass}`;
          health.textContent = roomErrorCount ? "有异常" : recordingCount ? "录制中" : checkingCount ? "检测中" : "待命";
        }
        const meterRing = document.getElementById("meterRing");
        if (meterRing) meterRing.style.setProperty("--recording-deg", `${ringDeg}deg`);
        const summary = document.getElementById("statusSummary");
        if (summary) {
          const systemMetrics = data.system_metrics || {};
          const memoryMetric = systemMetrics.memory || {};
          const diskMetric = systemMetrics.disk || {};
          const resourcePills = [
            resourcePill("CPU", systemMetrics.cpu || {}, "CPU 使用率"),
            resourcePill("内存", memoryMetric, `内存 ${fmtGb(memoryMetric.used_gb)} / ${fmtGb(memoryMetric.total_gb)}`),
            resourcePill("硬盘", diskMetric, `硬盘剩余 ${fmtGb(diskMetric.free_gb)} / ${fmtGb(diskMetric.total_gb)}${diskMetric.path ? ` · ${diskMetric.path}` : ""}`)
          ];
          summary.innerHTML = [
            `<span class="pill good">录制 ${recordingCount}</span>`,
            `<span class="pill warn">等待 ${waitingCount}</span>`,
            `<span class="pill info">检测 ${checkingCount}</span>`,
            `<span class="pill info">时长 ${fmtDuration(totalRecordingSeconds)}</span>`,
            ...resourcePills,
            `<span class="pill">停用 ${disabledCount}</span>`,
            `<span class="pill bad">错误 ${roomErrorCount}</span>`
          ].join("");
        }
        renderHomeDistributions(rooms, {
          recording: recordingDistributionCount,
          waiting: waitingCount,
          checking: checkingCount,
          disabled: disabledCount,
          error: roomErrorCount,
          other: otherStatusCount
        });

        state.delayDefault = delay;
        state.monitoringCount = monitoringCount;
        state.checkingCount = checkingCount;
        state.nextScanAtMs = Number(data.next_check_seconds || 0) > 0
          ? Date.now() + Number(data.next_check_seconds || 0) * 1000
          : 0;
        renderNextScanMetric();
        state.statusByUrl = new Map(rooms.map(item => [item.url, item]));
        state.recordingByUrl = new Map(recording.filter(item => item.url).map(item => [item.url, item]));
        state.history = data.history || {};
	        renderHistoryTrend(state.history);
	        renderMonitor(rooms);
	        refreshRoomStatusCells();
	        restorePageScroll(scrollSnapshot);
	      } catch (error) {
	        console.warn(error);
	        const health = document.getElementById("dashboardHealth");
	        if (health) {
	          health.className = "status error";
	          health.textContent = "连接异常";
	        }
	        const staleSeconds = lastStatusOkAt ? Math.max(1, Math.round((Date.now() - lastStatusOkAt) / 1000)) : 0;
	        setText(
	          "dashboardCopy",
	          staleSeconds ? `状态刷新超时，上次成功 ${staleSeconds}s 前。` : "暂时无法读取运行状态，正在重试。"
	        );
	        if (!quiet) toast(error.message || "状态读取失败");
	      } finally {
	        statusRequestInFlight = false;
	      }
    }
    function sortedMonitorRows(rows) {
      return [...rows].sort((left, right) => {
        const priority = statusPriority(left.status) - statusPriority(right.status);
        if (priority) return priority;
        const rightStats = roomRecordingStats(right);
        const leftStats = roomRecordingStats(left);
        if (rightStats.elapsedSeconds !== leftStats.elapsedSeconds) {
          return rightStats.elapsedSeconds - leftStats.elapsedSeconds;
        }
        return String(right.last_checked_at || "").localeCompare(String(left.last_checked_at || ""));
      });
    }
    function renderMonitor(rows) {
      const panel = document.getElementById("recentMonitorPanel");
      const tbody = document.getElementById("monitorRows");
      const hint = document.getElementById("monitorHint");
	      if (!panel && !tbody) return;
	      const sortedRows = sortedMonitorRows(rows);
	      const visibleRows = sortedRows;
	      state.monitorRows = rows;
	      const pageSize = state.monitorPageSize || 10;
	      const totalPages = Math.max(1, Math.ceil(visibleRows.length / pageSize));
	      state.monitorPage = Math.min(Math.max(1, state.monitorPage || 1), totalPages);
	      const pageStart = (state.monitorPage - 1) * pageSize;
	      const pageEnd = Math.min(pageStart + pageSize, visibleRows.length);
	      if (hint) {
	        hint.textContent = visibleRows.length
	          ? `第 ${state.monitorPage}/${totalPages} 页 · ${pageStart + 1}-${pageEnd} / ${visibleRows.length}`
	          : "暂无主播状态";
	      }
	      if (panel) {
	        const monitorCards = visibleRows.slice(pageStart, pageEnd);
	        if (!monitorCards.length) {
	          panel.innerHTML = `<div class="muted">暂无主播状态</div>`;
	        } else {
	          panel.innerHTML = `<div class="recent-card-list">` + monitorCards.map(focus => {
            const stats = roomRecordingStats(focus);
            const recording = state.recordingByUrl.get(focus.url) || {};
	            const isRecording = ["recording", "live"].includes(focus.status) || Boolean(recording.started_at);
	            const name = roomDisplayName(focus);
	            const group = focus.group || focus.configured_group || focus.platform || "其他";
	            const detail = String(focus.message || "").replace(/https?:\/\/\S+/g, "").replace(/[\\s/]+$/g, "").trim();
	            const avatarUrl = focus.avatar_url || recording.avatar_url || "";
	            const avatarLabel = String(name || "主").trim().slice(0, 1) || "主";
	            const avatarMarkup = avatarUrl
	              ? `<img class="recent-avatar" src="${escapeHtml(avatarUrl)}" alt="" loading="lazy" onerror="this.remove()">`
	              : "";
	            const actionMarkup = recentMonitorActionsMarkup(focus);
	            const tooltip = [
	              name,
	              `状态：${statusLabel(focus.status)}`,
	              `画质：${focus.quality || "-"}`,
	              `分组：${group}`,
	              `时长：${stats.elapsedSeconds ? fmtDuration(stats.elapsedSeconds) : "-"}`,
	              `开播：${formatStartTime(stats.startedAt)}`,
	              `检查：${formatCheckTime(focus.last_checked_at || "") || "-"}`,
	              detail
	            ].filter(Boolean).join(" · ");
	            return `
	              <article class="recent-card ${isRecording ? "recording" : ""}" title="${escapeHtml(tooltip)}">
	                <div class="recent-avatar-wrap">
	                  ${avatarMarkup}
	                  <span class="recent-avatar-fallback">${escapeHtml(avatarLabel)}</span>
	                </div>
	                <div class="recent-detail">
                  <div class="recent-title-row">
                    <h3 class="recent-title" title="${escapeHtml(name)}">${escapeHtml(name)}</h3>
                    <span class="status ${statusClass(focus.status)}">${statusLabel(focus.status)}</span>
                  </div>
                  <div class="recent-meta-grid">
                    <span>画质：${escapeHtml(focus.quality || "-")}</span>
                    <span>时长：${stats.elapsedSeconds ? fmtDuration(stats.elapsedSeconds) : "-"}</span>
                    <span>检查：${escapeHtml(formatCheckTime(focus.last_checked_at || "")) || "-"}</span>
                  </div>
                </div>
                  ${actionMarkup}
	              </article>
	            `;
	          }).join("") + `</div>
	            <div class="monitor-pager">
	              <button type="button" data-monitor-page="prev" ${state.monitorPage <= 1 ? "disabled" : ""}>上一页</button>
	              <span>${state.monitorPage} / ${totalPages}</span>
	              <button type="button" data-monitor-page="next" ${state.monitorPage >= totalPages ? "disabled" : ""}>下一页</button>
	            </div>`;
	        }
	      }
      if (!tbody) return;
      tbody.innerHTML = visibleRows.length ? visibleRows.map((row, index) => {
        const stats = roomRecordingStats(row);
        const detailParts = [row.group || row.configured_group || "", row.message || row.platform || row.url || ""]
          .filter(Boolean);
        const detail = detailParts.join(" / ");
        return `
          <tr>
            <td><span class="status ${statusClass(row.status)}">${statusLabel(row.status)}</span></td>
            <td>
              <div class="monitor-name" title="${escapeHtml(roomDisplayName(row))}">
                ${index + 1}. ${escapeHtml(roomDisplayName(row))}
                ${detail ? `<small title="${escapeHtml(detail)}">${escapeHtml(detail)}</small>` : ""}
              </div>
            </td>
            <td>${escapeHtml(row.quality || "")}</td>
            <td class="time-cell">${escapeHtml(formatStartTime(stats.startedAt))}</td>
            <td class="time-cell">${stats.elapsedSeconds ? `<span class="metric-chip">${fmtDuration(stats.elapsedSeconds)}</span>` : "-"}</td>
            <td class="time-cell">${escapeHtml(formatCheckTime(row.last_checked_at || ""))}</td>
            <td class="monitor-action">
              <div class="monitor-row-actions">${monitorRoomActionButtons(row)}</div>
            </td>
          </tr>
        `;
      }).join("") : `<tr><td colspan="7" class="muted">暂无主播状态</td></tr>`;
    }
    function renderRecording(rows) {
      const hint = document.getElementById("recordingHint");
      const tbody = document.getElementById("recordingRows");
      if (!hint || !tbody) return;
      const sortedRows = sortedRecordingRows(rows);
      const visibleRows = sortedRows.slice(0, 20);
      hint.textContent = rows.length
        ? (rows.length > visibleRows.length ? `显示 ${visibleRows.length} / ${rows.length} 个任务` : `${rows.length} 个任务`)
        : "暂无录制任务";
      updateRecordingSortHeaders();
      tbody.innerHTML = visibleRows.length ? visibleRows.map(row => `
        <tr>
          <td>${escapeHtml(row.name)}</td>
          <td>${escapeHtml(row.quality || "")}</td>
          <td>${fmtDuration(row.elapsed_seconds)}</td>
          <td>
            <button class="stop-recording danger" data-url="${escapeHtml(row.url || "")}" ${row.url ? "" : "disabled"}>停止</button>
          </td>
        </tr>
      `).join("") : `<tr><td colspan="4" class="muted">没有正在录制的直播</td></tr>`;
    }
    function renderRoomStatuses(rows) {
      const sortedRows = [...rows].sort((left, right) => {
        const priority = statusPriority(left.status) - statusPriority(right.status);
        if (priority) return priority;
        return String(right.last_checked_at || "").localeCompare(String(left.last_checked_at || ""));
      });
      const visibleRows = sortedRows.slice(0, 20);
      const hint = document.getElementById("statusLimitHint");
      const tbody = document.getElementById("roomStatusRows");
      if (!tbody) return;
      if (hint) hint.textContent = rows.length > visibleRows.length ? `重点显示 ${visibleRows.length} / ${rows.length}` : "自动刷新";
      tbody.innerHTML = visibleRows.length ? visibleRows.map(row => {
        const stats = roomRecordingStats(row);
        return `
          <tr>
            <td><span class="status ${statusClass(row.status)}">${statusLabel(row.status)}</span></td>
            <td>${escapeHtml(roomDisplayName(row))}</td>
            <td class="time-cell">${escapeHtml(formatStartTime(stats.startedAt))}</td>
            <td class="time-cell">${stats.elapsedSeconds ? fmtDuration(stats.elapsedSeconds) : "-"}</td>
            <td class="time-cell">${escapeHtml(formatCheckTime(row.last_checked_at || ""))}</td>
          </tr>
        `;
      }).join("") : `<tr><td colspan="5" class="muted">暂无状态数据</td></tr>`;
    }
    async function loadRooms() {
      const { data } = await api("/api/rooms");
      state.rooms = data;
      const existingIds = new Set(state.rooms.map(room => Number(room.id)));
      state.selectedRoomIds = new Set(Array.from(state.selectedRoomIds).filter(id => existingIds.has(Number(id))));
      renderRooms();
    }
    function resetRoomFilters() {
      state.roomSearch = "";
      state.roomGroupFilter = "";
      state.roomStatusFilter = "";
      state.roomPage = 1;
      const search = document.getElementById("roomSearch");
      const group = document.getElementById("roomGroupFilter");
      const status = document.getElementById("roomStatusFilter");
      if (search) search.value = "";
      if (group) group.value = "";
      if (status) status.value = "";
    }
    function roomEffectiveStatus(room) {
      const status = state.statusByUrl.get(room.url) || {};
      return room.enabled ? (status.status || "monitoring") : "disabled";
    }
	    function roomGroup(room) {
	      const status = state.statusByUrl.get(room.url) || {};
	      return room.group || status.group || status.configured_group || status.platform || "其他";
	    }
	    function roomAvatarMarkup(room, status = {}) {
	      const labelSource = status.anchor_name || room.name || status.configured_name || "主";
	      const label = String(labelSource || "主").trim().slice(0, 1) || "主";
	      const avatarUrl = status.avatar_url || room.avatar_url || "";
	      return `
	        <span class="room-avatar fallback ${avatarUrl ? "hidden" : ""}">${escapeHtml(label)}</span>
	        ${avatarUrl ? `<img class="room-avatar" src="${escapeHtml(avatarUrl)}" alt="" loading="lazy" onerror="this.previousElementSibling.classList.remove('hidden');this.remove()">` : ""}
	      `;
	    }
	    function roomGroups() {
	      return Array.from(new Set(state.rooms.map(room => roomGroup(room)).filter(Boolean)))
	        .sort((left, right) => left.localeCompare(right, "zh-Hans-CN", { numeric: true }));
    }
    function renderRoomGroupFilter() {
      const select = document.getElementById("roomGroupFilter");
      if (!select) return;
      const groups = roomGroups();
      const current = state.roomGroupFilter;
      const values = current && !groups.includes(current) ? [current, ...groups] : groups;
      select.innerHTML = `<option value="">全部分组</option>` + values.map(group => `
        <option value="${escapeHtml(group)}" ${group === current ? "selected" : ""}>${escapeHtml(group)}</option>
      `).join("");
      select.value = current;
    }
    function filteredRooms() {
      const query = state.roomSearch.trim().toLowerCase();
      return state.rooms.filter(room => {
        const effective = roomEffectiveStatus(room);
        const group = roomGroup(room);
        if (state.roomGroupFilter && group !== state.roomGroupFilter) return false;
        if (state.roomStatusFilter && effective !== state.roomStatusFilter) return false;
        if (!query) return true;
        const status = state.statusByUrl.get(room.url) || {};
        const haystack = [
          group,
          room.owner,
          room.name,
          room.url,
          room.quality,
          status.anchor_name,
          status.configured_name,
          status.configured_group,
          status.group,
          status.platform,
          status.record_name,
          statusLabel(effective)
        ].join(" ").toLowerCase();
        return haystack.includes(query);
      });
    }
    function currentRoomPageRows(filtered = filteredRooms()) {
      const totalPages = Math.max(1, Math.ceil(filtered.length / state.roomPageSize));
      state.roomPage = Math.min(Math.max(1, state.roomPage), totalPages);
      const start = (state.roomPage - 1) * state.roomPageSize;
      return { rows: filtered.slice(start, start + state.roomPageSize), filtered, totalPages };
    }
    function updateRoomOverview(filtered = filteredRooms()) {
      const total = state.rooms.length;
      const groups = roomGroups();
      const enabled = state.rooms.filter(room => room.enabled).length;
      const disabled = Math.max(0, total - enabled);
      const recording = state.rooms.filter(room => ["recording", "live"].includes(roomEffectiveStatus(room))).length;
      const checking = state.rooms.filter(room => roomEffectiveStatus(room) === "checking").length;
      const selected = state.selectedRoomIds.size;
      setText("roomTotalMetric", total);
      setText("roomTotalSub", groups.length ? `${groups.length} 个分组` : "暂无分组");
      setText("roomEnabledMetric", enabled);
      setText("roomEnabledSub", disabled ? `${disabled} 个停用` : (total ? "全部启用" : "等待添加"));
      setText("roomRecordingMetric", recording);
      setText("roomRecordingSub", checking ? `检测 ${checking} 个` : "实时状态");
      setText("roomSelectedMetric", selected);
      setText("roomSelectedSub", `${filtered.length} 个筛选结果`);
    }
    function updateRoomPager(rows, filtered, totalPages) {
      const first = filtered.length ? (state.roomPage - 1) * state.roomPageSize + 1 : 0;
      const last = filtered.length ? first + rows.length - 1 : 0;
      const selectAll = document.getElementById("selectAllRooms");
      const pageIds = rows.map(room => Number(room.id));
      const selectedOnPage = pageIds.filter(id => state.selectedRoomIds.has(id)).length;
      if (selectAll) {
        selectAll.checked = pageIds.length > 0 && selectedOnPage === pageIds.length;
        selectAll.indeterminate = selectedOnPage > 0 && selectedOnPage < pageIds.length;
      }
      setText("roomListSummary", `共 ${state.rooms.length} 个，筛选 ${filtered.length} 个，显示 ${first}-${last}，已选 ${state.selectedRoomIds.size} 个`);
      setText("roomPageInfo", `第 ${state.roomPage} / ${totalPages} 页`);
      updateRoomOverview(filtered);
      const prev = document.getElementById("roomPrevPage");
      const next = document.getElementById("roomNextPage");
      if (prev) prev.disabled = state.roomPage <= 1;
      if (next) next.disabled = state.roomPage >= totalPages;
    }
    function renderRooms() {
      const tbody = document.getElementById("roomRows");
      if (!tbody) return;
      renderRoomGroupFilter();
      const { rows, filtered, totalPages } = currentRoomPageRows();
	      tbody.innerHTML = rows.length ? rows.map(room => {
	        const effective = roomEffectiveStatus(room);
	        const checked = state.selectedRoomIds.has(Number(room.id)) ? "checked" : "";
	        const group = roomGroup(room);
	        const status = state.statusByUrl.get(room.url) || {};
	        return `
	          <tr data-id="${room.id}">
            <td><input class="room-select" type="checkbox" data-id="${room.id}" ${checked}></td>
            <td><span class="status ${statusClass(effective)}">${statusLabel(effective)}</span></td>
            <td><select class="room-priority" title="★★★ 约60秒巡检；★★ 约300秒巡检；★ 约600秒巡检">${priorityOptions(room.priority || "")}</select></td>
            <td><input class="room-group" value="${escapeHtml(group)}"></td>
            <td data-admin-only><input class="room-owner" value="${escapeHtml(room.owner || "")}"></td>
            <td><select class="room-quality">${optionList(room.quality)}</select></td>
            <td><input class="room-subtitle" type="checkbox" ${room.record_subtitle ? "checked" : ""}></td>
            <td><input class="room-burn-subtitle" type="checkbox" ${room.burn_subtitle ? "checked" : ""}></td>
            <td><input class="room-url" value="${escapeHtml(room.url)}"></td>
	            <td>
	              <div class="room-anchor-cell">
	                <span class="room-anchor-avatar">${roomAvatarMarkup(room, status)}</span>
	                <input class="room-name" value="${escapeHtml(room.name || "")}">
	              </div>
	            </td>
            <td>
              <div class="row-actions">
                <label title="启用"><input class="room-enabled" type="checkbox" ${room.enabled ? "checked" : ""}></label>
                <button class="save-room">保存</button>
                <button class="delete-room danger">删除</button>
              </div>
            </td>
          </tr>
        `;
      }).join("") : `<tr><td colspan="11" class="muted">${state.rooms.length ? "没有匹配的直播间" : "暂无直播间"}</td></tr>`;
      updateRoomPager(rows, filtered, totalPages);
    }
    function refreshRoomStatusCells() {
      document.querySelectorAll("#roomRows tr[data-id]").forEach(row => {
        const room = state.rooms.find(item => String(item.id) === String(row.dataset.id));
        if (!room) return;
        const effective = roomEffectiveStatus(room);
	        const badge = row.querySelector(".status");
	        if (badge) {
	          badge.className = `status ${statusClass(effective)}`;
	          badge.textContent = statusLabel(effective);
	        }
	        const avatar = row.querySelector(".room-anchor-avatar");
	        if (avatar) {
	          avatar.innerHTML = roomAvatarMarkup(room, state.statusByUrl.get(room.url) || {});
	        }
	      });
      updateRoomOverview();
    }
    function selectedIds() {
      return Array.from(state.selectedRoomIds);
    }
    async function saveRoom(row) {
      const id = Number(row.dataset.id);
      const body = {
        quality: row.querySelector(".room-quality").value,
        priority: row.querySelector(".room-priority").value,
        group: row.querySelector(".room-group").value.trim(),
        url: row.querySelector(".room-url").value.trim(),
        name: row.querySelector(".room-name").value.trim(),
        record_subtitle: row.querySelector(".room-subtitle").checked,
        burn_subtitle: row.querySelector(".room-burn-subtitle").checked,
        enabled: row.querySelector(".room-enabled").checked
      };
      if (isAdmin()) body.owner = row.querySelector(".room-owner")?.value.trim() || "";
      await api(`/api/rooms/${id}`, { method: "PUT", body: JSON.stringify(body) });
      toast("已保存直播间");
      await loadRooms();
    }
    async function deleteRoom(id) {
      await api(`/api/rooms/${id}`, { method: "DELETE" });
      state.selectedRoomIds.delete(Number(id));
      toast("已删除直播间");
      await loadRooms();
    }
    async function stopRecording(url) {
      if (!url) return toast("缺少直播间 URL");
      await api("/api/recording/stop", { method: "POST", body: JSON.stringify({ url }) });
      toast("已发送停止请求");
      await Promise.all([loadRooms(), loadStatus()]);
    }
    async function handleMonitorRoomAction(button) {
      const roomId = Number(button.dataset.roomId || 0);
      const action = button.dataset.monitorAction;
      const name = button.dataset.roomName || "直播间";
      if (!roomId) {
        toast("未找到直播间配置");
        return;
      }
      const deleteAfterDisable = action === "disable-delete";
      if (deleteAfterDisable) {
        const confirmed = await confirmDialog({
          title: "停用并删除",
          hint: name,
          message: `确定要停用并删除「${name}」吗？删除后会从直播间配置中移除。`,
          confirmText: "确认删除",
          danger: true
        });
        if (!confirmed) return;
      }
      const actionWrap = button.closest(".recent-actions, .monitor-row-actions");
      const actionButtons = actionWrap ? Array.from(actionWrap.querySelectorAll("[data-monitor-action]")) : [button];
      actionButtons.forEach(item => item.disabled = true);
      try {
        await api("/api/rooms/batch", {
          method: "PATCH",
          body: JSON.stringify({ ids: [roomId], changes: { enabled: false } })
        });
        if (deleteAfterDisable) {
          await api(`/api/rooms/${roomId}`, { method: "DELETE" });
          state.selectedRoomIds.delete(roomId);
          toast("已停用并删除直播间");
        } else {
          toast("已停用直播间");
        }
        await Promise.all([loadRooms(), loadStatus()]);
      } finally {
        actionButtons.forEach(item => item.disabled = false);
      }
    }
    async function setAllRoomsEnabled(enabled) {
      const buttons = [document.getElementById("enableAllRooms"), document.getElementById("stopAllRooms")].filter(Boolean);
      buttons.forEach(button => button.disabled = true);
      try {
        const rooms = state.rooms.length ? state.rooms : (await api("/api/rooms")).data;
        const ids = rooms.map(room => room.id);
        if (!ids.length) {
          toast("暂无直播间");
          return;
        }
        const actionText = enabled ? "启用" : "停用";
        const confirmed = await confirmDialog({
          title: `全部${actionText}`,
          hint: `${ids.length} 个直播间`,
          message: `确定要${actionText}全部 ${ids.length} 个直播间吗？此操作会立即修改当前可见的全部直播间状态。`,
          confirmText: `确认${actionText}`,
          danger: !enabled
        });
        if (!confirmed) {
          return;
        }
        await api("/api/rooms/batch", {
          method: "PATCH",
          body: JSON.stringify({ ids, changes: { enabled } })
        });
        toast(enabled ? "已启用全部直播间" : "已停用全部直播间");
        await Promise.all([loadRooms(), loadStatus()]);
      } finally {
        buttons.forEach(button => button.disabled = false);
      }
    }
    function downloadTextFile(filename, text) {
      const blob = new Blob([text || ""], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename || "URL_config.ini";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    }
    async function exportRoomsConfig() {
      const payload = await api("/api/rooms/export");
      const data = payload.data || {};
      if (!data.text) return toast("暂无直播间配置");
      downloadTextFile(data.filename, data.text);
      toast(`已导出 ${data.count || 0} 个直播间`);
    }
    async function importRoomsConfig(file) {
      if (!file) return;
      const text = await file.text();
      if (!text.trim()) return toast("导入文件为空");
      const result = await api("/api/rooms/import", { method: "POST", body: JSON.stringify({ text }) });
      resetRoomFilters();
      toast(`已导入或更新 ${result.count || 0} 个直播间`);
      await loadRooms();
    }
    function sitePickerOptions() {
      return [{ id: "*", name: "全部平台" }, ...(state.siteOptions || [])];
    }
    function renderSiteChecks(container, selectedSites = [], name = "site") {
      if (!container) return;
      const selected = new Set(selectedSites || []);
      container.innerHTML = sitePickerOptions().map(site => `
        <label class="site-check">
          <input type="checkbox" name="${name}" value="${escapeHtml(site.id)}" ${selected.has(site.id) ? "checked" : ""}>
          ${escapeHtml(site.name)}
        </label>
      `).join("");
    }
    function selectedSites(container) {
      const values = Array.from(container.querySelectorAll("input[type='checkbox']:checked")).map(input => input.value);
      return values.includes("*") ? ["*"] : values;
    }
    function resetUserForm() {
      document.getElementById("userUsername").value = "";
      document.getElementById("userPassword").value = "";
      document.getElementById("userRemark").value = "";
      document.getElementById("userEnabled").checked = true;
      renderSiteChecks(document.getElementById("userSiteGrid"), []);
    }
	    async function loadUsers() {
	      if (!isAdmin()) return;
	      const usersPayload = await api("/api/users");
	      state.users = usersPayload.data || [];
	      state.siteOptions = usersPayload.sites || state.siteOptions || [];
	      renderUserMetric();
	      renderUserSiteGrid();
	      renderUsers();
	    }
	    function renderUserSiteGrid() {
	      renderSiteChecks(document.getElementById("userSiteGrid"), []);
	    }
	    function managedUserByUsername(username) {
	      return state.users.find(user => user.username === username) || null;
	    }
	    function managedRowByUsername(username) {
	      return Array.from(document.querySelectorAll("#userRows tr[data-username]"))
	        .find(row => row.dataset.username === username) || null;
	    }
	    function managedUserSites(username) {
	      const user = managedUserByUsername(username);
	      return Array.isArray(user?.allowed_sites) ? user.allowed_sites : [];
	    }
	    function permissionNames(selectedSites = []) {
	      const selected = new Set(selectedSites || []);
	      if (selected.has("*")) return ["全部平台"];
	      return sitePickerOptions()
	        .filter(site => site.id !== "*" && selected.has(site.id))
	        .map(site => site.name);
	    }
	    function permissionSummary(selectedSites = []) {
	      if ((selectedSites || []).includes("*")) return "全部平台";
	      const names = permissionNames(selectedSites);
	      if (!names.length) return "未授权";
	      if (names.length <= 2) return names.join("、");
	      return `${names.slice(0, 2).join("、")} 等 ${names.length} 个`;
	    }
	    function permissionTitle(selectedSites = []) {
	      const names = permissionNames(selectedSites);
	      return names.length ? names.join("、") : "未授权平台";
	    }
	    function renderUsers() {
	      const tbody = document.getElementById("userRows");
	      if (!tbody) return;
	      tbody.innerHTML = state.users.length ? state.users.map(user => {
	        const allowedSites = Array.isArray(user.allowed_sites) ? user.allowed_sites : [];
	        return `
	        <tr data-username="${escapeHtml(user.username)}">
	          <td><strong>${escapeHtml(user.username)}</strong></td>
	          <td><input class="managed-enabled" type="checkbox" ${user.enabled ? "checked" : ""}></td>
	          <td><input class="managed-password" type="password" autocomplete="new-password" placeholder="留空不改"></td>
	          <td><input class="managed-remark" value="${escapeHtml(user.remark || "")}"></td>
	          <td class="user-permissions">
	            <div class="permission-summary">
	              <span class="permission-summary-text" title="${escapeHtml(permissionTitle(allowedSites))}">${escapeHtml(permissionSummary(allowedSites))}</span>
	              <button class="edit-managed-sites" type="button">权限</button>
	            </div>
	          </td>
	          <td>
	            <div class="row-actions">
	              <button class="save-managed-user" type="button">保存</button>
	              <button class="delete-managed-user danger" type="button">删除</button>
	            </div>
	          </td>
	        </tr>
	      `;
	      }).join("") : `<tr><td colspan="6" class="muted">暂无用户</td></tr>`;
	    }
    async function saveUserFromForm() {
      const body = {
        username: document.getElementById("userUsername").value.trim(),
        password: document.getElementById("userPassword").value,
        enabled: document.getElementById("userEnabled").checked,
        remark: document.getElementById("userRemark").value.trim(),
        allowed_sites: selectedSites(document.getElementById("userSiteGrid"))
      };
      if (!body.username) return toast("用户名不能为空");
      await api("/api/users", { method: "POST", body: JSON.stringify(body) });
      toast("已保存用户");
      resetUserForm();
      await loadUsers();
    }
	    function managedUserPayload(row, allowedSites = null) {
	      const username = row.dataset.username;
	      const user = managedUserByUsername(username) || {};
	      return {
	        password: row.querySelector(".managed-password").value,
	        enabled: row.querySelector(".managed-enabled").checked,
	        remark: row.querySelector(".managed-remark").value.trim(),
	        allowed_sites: allowedSites || (Array.isArray(user.allowed_sites) ? user.allowed_sites : [])
	      };
	    }
	    async function saveManagedUser(row, allowedSites = null) {
	      const username = row.dataset.username;
	      const body = managedUserPayload(row, allowedSites);
	      await api(`/api/users/${encodeURIComponent(username)}`, { method: "PUT", body: JSON.stringify(body) });
	      toast("已保存用户");
	      await loadUsers();
	    }
	    function openManagedSiteEditor(row) {
	      const username = row.dataset.username;
	      const user = managedUserByUsername(username);
	      if (!user) return toast("用户不存在");
	      state.siteEditorUsername = username;
	      document.getElementById("siteEditorUser").textContent = username;
	      renderSiteChecks(document.getElementById("managedSiteEditorGrid"), managedUserSites(username), "managed-site");
	      document.getElementById("siteEditor").hidden = false;
	      document.getElementById("saveSiteEditor").focus();
	    }
	    function closeManagedSiteEditor() {
	      state.siteEditorUsername = "";
	      document.getElementById("siteEditor").hidden = true;
	      document.getElementById("managedSiteEditorGrid").innerHTML = "";
	    }
	    async function saveManagedSiteEditor() {
	      const username = state.siteEditorUsername;
	      if (!username) return;
	      const row = managedRowByUsername(username);
	      if (!row) return toast("用户不存在");
	      const allowedSites = selectedSites(document.getElementById("managedSiteEditorGrid"));
	      await saveManagedUser(row, allowedSites);
	      closeManagedSiteEditor();
	    }
    async function deleteManagedUser(username) {
      await api(`/api/users/${encodeURIComponent(username)}`, { method: "DELETE" });
      toast("已删除用户");
      await loadUsers();
      await loadRooms().catch(() => {});
    }
	    async function loadConfig() {
      if (!isAdmin()) return;
      const { data } = await api("/api/config");
      state.config = data;
      if (!state.currentSection && data.length) state.currentSection = data[0].name;
      renderConfig();
    }
	    function configGroupName(section, key) {
      if (section === "录制设置") {
        if (/保存路径|保存文件夹|保存文件名|名称中的表情|标题/.test(key)) return "保存路径与命名";
        if (/视频保存格式|原画|分段|mp4|h264|字幕|剩余阈值|删除原文件|追加格式|转码/.test(key)) return "画质格式与后处理";
        if (/代理|线程数|循环|随机浮动|排队|直播源|https|重载|进程检查|状态面板|刷新/.test(key)) return "巡检与代理";
        if (/自定义脚本/.test(key)) return "自定义脚本";
        return "基础设置";
	      }
	      if (section === "推送配置") {
	        if (/资源告警|cpu告警|CPU告警|内存告警|硬盘告警/.test(key)) return "系统资源告警";
	        return "TG Bot";
	      }
      if (section === "Cookie") {
        if (/抖音|快手|虎牙|斗鱼|yy|b站|小红书|网易|千度|猫耳|百度|微博|酷狗|花椒|流星|acfun|畅聊|音播|映客|知乎|嗨秀|淘宝|京东|咪咕|来秀/.test(key)) return "国内平台 Cookie";
        if (/tiktok|bigo|blued|soop|panda|wink|flex|look|twit|twitch|liveme|showroom|chzzk|shopee|youtube|faceit|picarto|17live|langlive|pplive|6room|lehai|huamao/.test(key.toLowerCase())) return "海外平台 Cookie";
        return "其他 Cookie";
      }
      if (section === "账号密码") {
        if (/twitcasting/.test(key)) return "TwitCasting";
        if (/popkontv|partner/.test(key)) return "PopkonTV";
        return "平台账号";
      }
      if (section === "WebUI") {
        if (/登录|会话/.test(key)) return "登录安全";
        return "服务监听";
      }
      if (section === "Authorization") return "授权令牌";
	      return section;
	    }
	    const interactionConfigKeys = new Set([
	      "tg bot token",
	      "tg聊天id(个人或者群组id)",
	      "系统资源告警开启(是/否)",
	      "CPU告警阈值(%)",
	      "cpu告警阈值(%)",
	      "内存告警阈值(%)",
	      "硬盘告警阈值(%)",
	      "系统资源告警检测间隔(秒)",
	      "系统资源告警冷却时间(秒)",
	      "tg机器人交互开启(是/否)",
	      "tg机器人允许聊天id(逗号分隔)",
	      "tg添加直播间归属用户"
	    ]);
	    function configSectionLabel(sectionName) {
	      return sectionName === "推送配置" ? "TG 与告警" : sectionName;
	    }
	    function shouldShowConfigItem(sectionName, item) {
	      if (sectionName === "推送配置") return interactionConfigKeys.has(item.key);
	      return true;
	    }
	    function configOptionValues(key, value) {
      if (key === "language(zh_cn/en)") return ["zh_cn", "en"];
      if (key.includes("视频保存格式")) return ["ts", "mkv", "flv", "mp4", "mp3音频", "m4a音频"];
      if (key === "录制完成后自动转为mp4格式") return ["否", "是"];
      if (key === "视频分段模式(时间/大小)") return ["时间", "大小"];
      if (key === "字幕内容类型(弹幕/时间)") return ["弹幕", "时间"];
      if (key.includes("原画|超清|高清|标清|流畅")) return ["原画", "超清", "高清", "标清", "流畅"];
      if (key === "bark推送中断级别") return ["", "active", "time-sensitive", "passive"];
      if (key === "twitcasting账号类型") return ["normal", "business"];
      if (/(是\/否)|是否|开启/.test(key) || ["是", "否"].includes(String(value || ""))) return ["", "是", "否"];
      return [];
    }
    function normalizedConfigValue(key, value) {
      const current = String(value || "");
      if (!current && key.includes("视频保存格式")) return "mp4";
      if (!current && key === "录制完成后自动转为mp4格式") return "否";
      return current;
    }
    function configFieldHint(item) {
      const key = item.key || "";
      const value = normalizedConfigValue(key, item.value);
      if (key.includes("视频保存格式") && value !== "mp4") {
        return `<p class="config-hint warn">当前不是 mp4，最终文件会按这里的格式保存。</p>`;
      }
      if (key === "录制完成后自动转为mp4格式") {
        return `<p class="config-hint">保存格式为 ts 时才需要设为 是；低 CPU 推荐直接把保存格式设为 mp4。</p>`;
      }
      return "";
    }
    function configInputType(key) {
      if (/端口|线程数|任务数|块大小|间隔|冷却|循环时间|排队读取|频率|会话有效期|分段时间/.test(key)) return "number";
      if (/阈值/.test(key)) return "number";
      return "text";
    }
    function isLongConfigField(item) {
      const key = item.key || "";
      const value = item.value || "";
      return item.sensitive || value.length > 90 || /cookie|平台|内容|命令|地址|接口|路径|token|令牌/i.test(key);
    }
    function renderConfigControl(sectionName, item, showSecrets) {
      const options = configOptionValues(item.key, item.value);
      if (options.length) {
        const current = normalizedConfigValue(item.key, item.value);
        const values = options.includes(current) ? options : [current, ...options];
        return `<select class="config-value">${values.map(value => `
          <option value="${escapeHtml(value)}" ${value === current ? "selected" : ""}>${value ? escapeHtml(value) : "未设置"}</option>
        `).join("")}</select>`;
      }
      if (isLongConfigField(item) && !(item.sensitive && !showSecrets)) {
        return `<textarea class="config-value">${escapeHtml(item.value)}</textarea>`;
      }
      const type = item.sensitive && !showSecrets ? "password" : configInputType(item.key);
      const step = /阈值/.test(item.key) ? ` step="0.1"` : "";
      return `<input class="config-value" type="${type}"${step} value="${escapeHtml(item.value)}">`;
    }
	    function renderConfig() {
	      const list = document.getElementById("sectionList");
	      list.innerHTML = state.config.map(section => `
	        <button class="section-btn ${section.name === state.currentSection ? "active" : ""}" data-section="${escapeHtml(section.name)}">
	          ${escapeHtml(configSectionLabel(section.name))}
	        </button>
	      `).join("");
	      const section = state.config.find(item => item.name === state.currentSection) || { items: [] };
	      const showSecrets = document.getElementById("showSecrets").checked;
	      const groups = new Map();
	      section.items.filter(item => shouldShowConfigItem(section.name, item)).forEach(item => {
        const group = configGroupName(section.name, item.key);
        if (!groups.has(group)) groups.set(group, []);
        groups.get(group).push(item);
      });
      document.getElementById("configCards").innerHTML = Array.from(groups.entries()).map(([group, items]) => {
        const isVisibleLong = item => isLongConfigField(item) && !(item.sensitive && !showSecrets);
        const wide = items.length > 8 || items.some(item => isVisibleLong(item));
        return `
          <article class="config-card ${wide ? "wide" : ""}" data-group="${escapeHtml(group)}">
            <div class="config-card-head">
              <div class="config-card-title">${escapeHtml(group)} <small>${items.length} 项</small></div>
              <button class="save-config-group" type="button">保存本组</button>
            </div>
            <div class="config-card-body">
              ${items.map(item => {
                const longClass = isVisibleLong(item) ? "long" : "";
                return `
                <div class="config-field ${longClass}" data-section="${escapeHtml(section.name)}" data-key="${escapeHtml(item.key)}">
	                  <label title="${escapeHtml(item.key)}">${escapeHtml(item.key)}</label>
	                  ${renderConfigControl(section.name, item, showSecrets)}
	                  ${configFieldHint(item)}
	                </div>
              `;
              }).join("")}
            </div>
          </article>
        `;
      }).join("") || `<div class="muted">暂无配置项</div>`;
    }
    async function saveConfigGroup(card) {
      const button = card.querySelector(".save-config-group");
      const fields = Array.from(card.querySelectorAll(".config-field"));
      if (!fields.length) return;
      button.disabled = true;
      try {
        for (const field of fields) {
          const body = {
            section: field.dataset.section,
            key: field.dataset.key,
            value: field.querySelector(".config-value").value
          };
          await api("/api/config", { method: "PUT", body: JSON.stringify(body) });
        }
        toast(`已保存 ${card.dataset.group || "本组"}`);
      } finally {
        button.disabled = false;
      }
      await loadConfig();
    }
    function openView(view) {
      if (["config", "users"].includes(view) && !isAdmin()) {
        toast("需要管理员权限");
        view = "status";
      }
      const button = document.querySelector(`.tab[data-view="${view}"]`);
      const panel = document.getElementById(`view-${view}`);
      if (!button || !panel) return;
      state.currentView = view;
      document.querySelectorAll(".tab").forEach(item => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      panel.classList.add("active");
      if (view === "rooms") loadRooms().catch(error => toast(error.message));
      if (view === "users") loadUsers().catch(error => toast(error.message));
      if (view === "config") loadConfig().catch(error => toast(error.message));
    }
    document.querySelectorAll(".tab").forEach(button => {
      button.addEventListener("click", () => openView(button.dataset.view));
    });
    document.getElementById("loginForm").addEventListener("submit", event => {
      event.preventDefault();
      const button = document.getElementById("loginButton");
      button.disabled = true;
      document.getElementById("loginError").textContent = "";
      login(
        document.getElementById("loginUsername").value.trim(),
        document.getElementById("loginPassword").value
      ).catch(error => {
        document.getElementById("loginError").textContent = error.message;
      }).finally(() => {
        button.disabled = false;
      });
    });
    document.getElementById("logoutButton").addEventListener("click", () => {
      logout().catch(error => toast(error.message));
    });
    document.getElementById("jumpRooms").addEventListener("click", () => openView("rooms"));
    document.getElementById("enableAllRooms").addEventListener("click", () => {
      setAllRoomsEnabled(true).catch(error => toast(error.message));
    });
    document.getElementById("stopAllRooms").addEventListener("click", () => {
      setAllRoomsEnabled(false).catch(error => toast(error.message));
    });
    document.getElementById("refreshDashboard").addEventListener("click", () => {
      Promise.all([loadStatus({ quiet: false }), loadRooms().catch(() => {})]).then(() => toast("仪表盘已刷新")).catch(error => toast(error.message));
    });
    document.getElementById("addUrl").addEventListener("paste", () => {
      setTimeout(() => fillShareText().catch(() => {}), 0);
    });
    document.getElementById("addUrl").addEventListener("blur", () => fillShareText().catch(() => {}));
	    document.getElementById("refreshRooms").addEventListener("click", () => loadRooms().catch(error => toast(error.message)));
	    document.getElementById("refreshUsers").addEventListener("click", () => loadUsers().catch(error => toast(error.message)));
	    document.getElementById("saveUser").addEventListener("click", () => saveUserFromForm().catch(error => toast(error.message)));
    document.getElementById("resetUserForm").addEventListener("click", resetUserForm);
	    document.getElementById("userRows").addEventListener("click", event => {
	      const row = event.target.closest("tr[data-username]");
	      if (!row) return;
	      if (event.target.classList.contains("edit-managed-sites")) {
	        openManagedSiteEditor(row);
	        return;
	      }
	      if (event.target.classList.contains("save-managed-user")) {
	        saveManagedUser(row).catch(error => toast(error.message));
	      }
	      if (event.target.classList.contains("delete-managed-user")) {
	        deleteManagedUser(row.dataset.username).catch(error => toast(error.message));
	      }
	    });
	    document.getElementById("closeSiteEditor").addEventListener("click", closeManagedSiteEditor);
	    document.getElementById("cancelSiteEditor").addEventListener("click", closeManagedSiteEditor);
	    document.getElementById("siteEditor").addEventListener("click", event => {
	      if (event.target.id === "siteEditor") closeManagedSiteEditor();
	    });
	    document.getElementById("closeConfirm").addEventListener("click", () => closeConfirmDialog(false));
	    document.getElementById("cancelConfirm").addEventListener("click", () => closeConfirmDialog(false));
	    document.getElementById("confirmAction").addEventListener("click", () => closeConfirmDialog(true));
	    document.getElementById("confirmDialog").addEventListener("click", event => {
	      if (event.target.id === "confirmDialog") closeConfirmDialog(false);
	    });
	    document.getElementById("saveSiteEditor").addEventListener("click", event => {
	      const button = event.currentTarget;
	      button.disabled = true;
	      saveManagedSiteEditor().catch(error => toast(error.message)).finally(() => {
	        button.disabled = false;
	      });
	    });
	    document.addEventListener("keydown", event => {
	      if (event.key === "Escape" && !document.getElementById("siteEditor").hidden) {
	        closeManagedSiteEditor();
	      }
	      if (event.key === "Escape" && !document.getElementById("confirmDialog").hidden) {
	        closeConfirmDialog(false);
	      }
	    });
	    document.getElementById("roomSearch").addEventListener("input", event => {
	      state.roomSearch = event.target.value;
	      state.roomPage = 1;
      renderRooms();
    });
    document.getElementById("roomGroupFilter").addEventListener("change", event => {
      state.roomGroupFilter = event.target.value;
      state.roomPage = 1;
      renderRooms();
    });
    document.getElementById("roomStatusFilter").addEventListener("change", event => {
      state.roomStatusFilter = event.target.value;
      state.roomPage = 1;
      renderRooms();
    });
    document.getElementById("roomPageSize").addEventListener("change", event => {
      state.roomPageSize = Number(event.target.value || 50);
      state.roomPage = 1;
      renderRooms();
    });
    document.getElementById("roomPrevPage").addEventListener("click", () => {
      state.roomPage = Math.max(1, state.roomPage - 1);
      renderRooms();
    });
    document.getElementById("roomNextPage").addEventListener("click", () => {
      state.roomPage += 1;
      renderRooms();
    });
    document.getElementById("addRoom").addEventListener("click", async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await fillShareText();
        const url = document.getElementById("addUrl").value.trim();
        if (!url) return toast("URL 不能为空");
        const result = await api("/api/rooms", { method: "POST", body: JSON.stringify({
          quality: document.getElementById("addQuality").value,
          priority: document.getElementById("addPriority").value,
          group: document.getElementById("addGroup").value.trim(),
          owner: isAdmin() ? document.getElementById("addOwner").value.trim() : "",
          url,
          name: document.getElementById("addName").value.trim(),
          record_subtitle: document.getElementById("addSubtitle").checked,
          burn_subtitle: document.getElementById("addBurnSubtitle").checked,
          enabled: document.getElementById("addEnabled").checked
        }) });
        document.getElementById("addUrl").value = "";
        document.getElementById("addName").value = "";
        document.getElementById("addGroup").value = "";
        if (document.getElementById("addOwner")) document.getElementById("addOwner").value = "";
        resetRoomFilters();
        toast(result.data && result.data.existing ? "直播间已存在，已更新" : "已添加直播间");
        await loadRooms();
      } catch (error) {
        toast(error.message);
      } finally {
        button.disabled = false;
      }
    });
    document.getElementById("batchAdd").addEventListener("click", async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const text = document.getElementById("batchText").value;
        if (!text.trim()) return toast("请输入直播间");
        const result = await api("/api/rooms/batch", { method: "POST", body: JSON.stringify({ text }) });
        document.getElementById("batchText").value = "";
        resetRoomFilters();
        toast(`已添加或更新 ${result.count || 0} 个直播间`);
        await loadRooms();
      } catch (error) {
        toast(error.message);
      } finally {
        button.disabled = false;
      }
    });
    document.getElementById("exportRooms").addEventListener("click", async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await exportRoomsConfig();
      } catch (error) {
        toast(error.message);
      } finally {
        button.disabled = false;
      }
    });
    document.getElementById("importRooms").addEventListener("click", () => {
      const input = document.getElementById("roomImportFile");
      input.value = "";
      input.click();
    });
    document.getElementById("roomImportFile").addEventListener("change", async event => {
      const file = event.target.files && event.target.files[0];
      const button = document.getElementById("importRooms");
      button.disabled = true;
      try {
        await importRoomsConfig(file);
      } catch (error) {
        toast(error.message);
      } finally {
        button.disabled = false;
        event.target.value = "";
      }
    });
    document.getElementById("applyBulk").addEventListener("click", async () => {
      const ids = selectedIds();
      if (!ids.length) return toast("请选择直播间");
      const enabledValue = document.getElementById("bulkEnabled").value;
      const priorityValue = document.getElementById("bulkPriority").value;
      const subtitleValue = document.getElementById("bulkSubtitle").value;
      const burnSubtitleValue = document.getElementById("bulkBurnSubtitle").value;
      const groupValue = document.getElementById("bulkGroup").value.trim();
      const changes = {
        quality: document.getElementById("bulkQuality").value,
        name: document.getElementById("bulkName").value.trim()
      };
      if (enabledValue) changes.enabled = enabledValue === "true";
      if (priorityValue) changes.priority = priorityValue;
      if (groupValue) changes.group = groupValue;
      if (subtitleValue) changes.record_subtitle = subtitleValue === "true";
      if (burnSubtitleValue) changes.burn_subtitle = burnSubtitleValue === "true";
      await api("/api/rooms/batch", { method: "PATCH", body: JSON.stringify({ ids, changes }) });
      toast("已批量修改");
      await loadRooms();
    });
    document.getElementById("deleteSelected").addEventListener("click", async () => {
      const ids = selectedIds().sort((a, b) => b - a);
      if (!ids.length) return toast("请选择直播间");
      for (const id of ids) await api(`/api/rooms/${id}`, { method: "DELETE" });
      ids.forEach(id => state.selectedRoomIds.delete(Number(id)));
      toast("已删除所选直播间");
      await loadRooms();
    });
    document.getElementById("selectAllRooms").addEventListener("change", event => {
      const { rows } = currentRoomPageRows();
      rows.forEach(room => {
        const id = Number(room.id);
        if (event.target.checked) state.selectedRoomIds.add(id);
        else state.selectedRoomIds.delete(id);
      });
      renderRooms();
    });
    document.getElementById("selectFilteredRooms").addEventListener("click", () => {
      filteredRooms().forEach(room => state.selectedRoomIds.add(Number(room.id)));
      renderRooms();
    });
    document.getElementById("clearRoomSelection").addEventListener("click", () => {
      state.selectedRoomIds.clear();
      renderRooms();
    });
    document.getElementById("roomRows").addEventListener("change", event => {
      if (!event.target.classList.contains("room-select")) return;
      const id = Number(event.target.dataset.id);
      if (event.target.checked) state.selectedRoomIds.add(id);
      else state.selectedRoomIds.delete(id);
      const { rows, filtered, totalPages } = currentRoomPageRows();
      updateRoomPager(rows, filtered, totalPages);
    });
    document.getElementById("roomRows").addEventListener("click", event => {
      const row = event.target.closest("tr[data-id]");
      if (!row) return;
      if (event.target.classList.contains("save-room")) saveRoom(row).catch(error => toast(error.message));
      if (event.target.classList.contains("delete-room")) deleteRoom(Number(row.dataset.id)).catch(error => toast(error.message));
    });
	    const recentMonitorPanel = document.getElementById("recentMonitorPanel");
	    if (recentMonitorPanel) {
	      recentMonitorPanel.addEventListener("click", event => {
	        const pageButton = event.target.closest("[data-monitor-page]");
	        if (pageButton) {
	          const totalPages = Math.max(1, Math.ceil((state.monitorRows || []).length / (state.monitorPageSize || 10)));
	          state.monitorPage += pageButton.dataset.monitorPage === "next" ? 1 : -1;
	          state.monitorPage = Math.min(Math.max(1, state.monitorPage), totalPages);
	          renderMonitor(state.monitorRows || []);
	          return;
	        }
	        const monitorAction = event.target.closest("[data-monitor-action]");
	        if (monitorAction) {
	          handleMonitorRoomAction(monitorAction).catch(error => toast(error.message));
	          return;
	        }
	        if (!event.target.classList.contains("stop-recording")) return;
	        stopRecording(event.target.dataset.url).catch(error => toast(error.message));
	      });
	    }
    const monitorRows = document.getElementById("monitorRows");
    if (monitorRows) {
      monitorRows.addEventListener("click", event => {
        const monitorAction = event.target.closest("[data-monitor-action]");
        if (!monitorAction) return;
        handleMonitorRoomAction(monitorAction).catch(error => toast(error.message));
      });
    }
    document.getElementById("historyRangeTabs").addEventListener("click", event => {
      const button = event.target.closest("[data-history-range]");
      if (!button) return;
      state.historyRange = button.dataset.historyRange;
      renderHistoryTrend(state.history);
    });
    document.getElementById("sectionList").addEventListener("click", event => {
      const button = event.target.closest(".section-btn");
      if (!button) return;
      state.currentSection = button.dataset.section;
      renderConfig();
    });
    document.getElementById("showSecrets").addEventListener("change", renderConfig);
    document.getElementById("configCards").addEventListener("click", event => {
      const button = event.target.closest(".save-config-group");
      if (!button) return;
      saveConfigGroup(button.closest(".config-card")).catch(error => toast(error.message));
    });
    renderSelects();
    resetUserForm();
    checkAuth();
    setInterval(() => {
      if (document.body.classList.contains("authenticated")) {
        loadStatus();
      }
    }, STATUS_REFRESH_MS);
    setInterval(() => {
      if (document.body.classList.contains("authenticated")) {
        renderNextScanMetric();
      }
    }, 1000);
  </script>
</body>
</html>
"""
