"""载荷纪元领域原语。

版本键不变而载荷变化时，用纪元与 SHA-256 载荷哈希把“同键但不同载荷”区分开。
本模块只放无 IO 的规范化/哈希函数，便于后端服务、核证与自动化共用同一口径。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

初始载荷纪元 = 1


INITIAL_EPOCH = 初始载荷纪元


def 规范化载荷正文(载荷: Any) -> str:
    """返回排序键、紧凑分隔的 canonical JSON 文本。

    数据库里可能已经存成 JSON 字符串；先尝试解析，避免仅因空格/键序不同
    把同一载荷误判成变更。无法解析的字符串按 JSON 字符串字面量参与哈希。
    """

    if isinstance(载荷, str):
        try:
            载荷 = json.loads(载荷)
        except (json.JSONDecodeError, TypeError):
            return json.dumps(载荷, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return json.dumps(载荷, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def 计算载荷哈希(载荷: Any) -> str:
    正文 = 规范化载荷正文(载荷)
    return hashlib.sha256(正文.encode("utf-8")).hexdigest()


def 规范化哈希值(哈希: Any) -> str:
    if 哈希 is None:
        return ""
    文本 = str(哈希).strip().lower()
    if 文本.startswith("sha256:"):
        文本 = 文本.split(":", 1)[1]
    return 文本


def 哈希相等(左: Any, 右: Any) -> bool:
    a = 规范化哈希值(左)
    b = 规范化哈希值(右)
    return bool(a) and a == b


def 短哈希(哈希: Any, 长度: int = 12) -> str:
    值 = 规范化哈希值(哈希)
    return 值[:长度]


def 下一纪元(当前: Any) -> int:
    try:
        return max(1, int(当前 or 0)) + 1
    except (TypeError, ValueError):
        return 初始载荷纪元 + 1



canonical_payload = 规范化载荷正文
canonical_payload_text = 规范化载荷正文
payload_hash = 计算载荷哈希
calculate_payload_hash = 计算载荷哈希
compute_payload_hash = 计算载荷哈希
normalize_hash = 规范化哈希值
normalize_payload_hash = 规范化哈希值
hash_equal = 哈希相等
hashes_equal = 哈希相等
next_epoch = 下一纪元
bump_epoch = 下一纪元
