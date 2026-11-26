from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.db import 连接
from app.modules.载荷纪元 import 计算载荷哈希, 哈希相等, 规范化哈希值


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 取任意(体: dict, *键s: str, 默认: Any = None, default: Any = None) -> Any:
    for 键 in 键s:
        if 键 in 体 and 体[键] is not None and 体[键] != "":
            return 体[键]
    return 默认 if 默认 is not None else default


def 取整数(体: dict, *键s: str, 默认: int | None = None, default: int | None = None) -> int | None:
    值 = 取任意(体, *键s, 默认=None)
    if 值 is None:
        return 默认 if 默认 is not None else default
    try:
        return int(值)
    except (TypeError, ValueError):
        raise HTTPException(400, f"纪元必须是整数:{键s[0]}={值!r}")


def 版本哈希(row: Any) -> str:
    存哈希 = ""
    try:
        存哈希 = row["载荷哈希"] or ""
    except (IndexError, KeyError):
        pass
    if 存哈希:
        return 规范化哈希值(存哈希)
    try:
        return 计算载荷哈希(row["载荷"])
    except (IndexError, KeyError, TypeError):
        return ""


def 版本纪元(row: Any) -> int:
    try:
        return max(1, int(row["载荷纪元"] or 1))
    except (IndexError, KeyError, TypeError, ValueError):
        return 1


def 票钉纪元(row: Any) -> int:
    for 键 in ("下发钉纪元", "钉纪元", "载荷纪元"):
        try:
            值 = row[键]
            if 值:
                return int(值)
        except (IndexError, KeyError, TypeError, ValueError):
            continue
    return 1


def 票钉哈希(row: Any) -> str:
    for 键 in ("下发钉哈希", "钉哈希", "载荷哈希"):
        try:
            值 = row[键]
            if 值:
                return 规范化哈希值(值)
        except (IndexError, KeyError, TypeError):
            continue
    return ""


def 记命运(conn, 对象类型: str, 对象键: str, 命运: str, 说明: str = "") -> None:
    conn.execute(
        "INSERT INTO 命运账(对象类型, 对象键, 命运, 时刻, 说明) VALUES (?,?,?,?,?)",
        (对象类型, 对象键, 命运, 此刻(), 说明),
    )


def 作废旧钉(
    conn,
    *,
    版本键: str,
    旧纪元: int,
    旧哈希: str,
    新纪元: int,
    新哈希: str,
    缘由: str = "载荷纪元抬升",
    说明: str = "",
) -> list[dict]:
    """把某版本下仍钉在旧纪元/旧哈希的非终态票作废，并落旧钉表与命运账。"""

    rows = conn.execute(
        """SELECT * FROM 下发票
           WHERE 版本键=? AND 状态 IN ('待下发','已下发','灰度中','回滚中')
           ORDER BY 票号""",
        (版本键,),
    ).fetchall()
    作废 = []
    for t in rows:
        t纪元 = 票钉纪元(t) or 旧纪元
        t哈希 = 票钉哈希(t) or 规范化哈希值(旧哈希)
        if t纪元 == 新纪元 and 哈希相等(t哈希, 新哈希):
            continue

        conn.execute("UPDATE 下发票 SET 状态='已作废' WHERE 票号=?", (t["票号"],))

        
        
        old_reads = conn.execute(
            "SELECT 证号 FROM 回读证 WHERE 票号=? AND 结果='确认'",
            (t["票号"],),
        ).fetchall()
        for rd in old_reads:
            conn.execute(
                """UPDATE 回读证
                   SET 结果='旁置', 有效=0, 旧纪元=1, 处置='纪元抬升自动旁置',
                       说明=CASE WHEN 说明='' THEN ? ELSE 说明 || '；' || ? END
                   WHERE 证号=?""",
                (
                    f"原确认落在旧纪元{t纪元}/{(t哈希 or '')[:12]}，载荷抬纪元后旁置",
                    f"原确认落在旧纪元{t纪元}/{(t哈希 or '')[:12]}，载荷抬纪元后旁置",
                    rd["证号"],
                ),
            )
            记命运(conn, "回读证", rd["证号"], "旁置", f"随旧钉{t['票号']}自动旁置")

        注记 = 说明 or f"载荷已从纪元{旧纪元}变更到{新纪元}，旧钉{t纪元}/{(t哈希 or '')[:12]}作废，须按新纪元重钉"
        cur = conn.execute(
            """INSERT INTO 作废旧钉
               (票号, 开关键, 版本键, 桶键, 旧纪元, 旧哈希, 新纪元, 新哈希, 缘由, 时刻, 说明)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                t["票号"], t["开关键"], 版本键, t["桶键"],
                t纪元, t哈希, 新纪元, 规范化哈希值(新哈希),
                缘由, 此刻(), 注记,
            ),
        )
        记命运(conn, "下发票", t["票号"], "作废", f"作废旧钉#{cur.lastrowid}:{注记}")
        作废.append({
            "旧钉编号": cur.lastrowid,
            "票号": t["票号"],
            "版本键": 版本键,
            "旧纪元": t纪元,
            "旧哈希": t哈希,
            "新纪元": 新纪元,
            "新哈希": 规范化哈希值(新哈希),
            "命运": "作废",
        })
    return 作废


def 票钉当前(conn, ticket: Any, version: Any | None = None) -> tuple[bool, str, int, str]:
    if version is None:
        version = conn.execute(
            "SELECT * FROM 开关版本 WHERE 版本键=?", (ticket["版本键"],)
        ).fetchone()
    if not version:
        return False, "版本悬空", 票钉纪元(ticket), 票钉哈希(ticket)
    pin_epoch = 票钉纪元(ticket)
    pin_hash = 票钉哈希(ticket)
    cur_epoch = 版本纪元(version)
    cur_hash = 版本哈希(version)
    if pin_epoch != cur_epoch or not 哈希相等(pin_hash, cur_hash):
        return False, "下发钉纪元/哈希不是当前载荷", pin_epoch, pin_hash
    return True, "", pin_epoch, pin_hash


def 核证(体: dict | None = None) -> dict:
    体 = 体 or {}
    conn = 连接()
    try:
        版本键 = 取任意(体, "版本键", "versionKey", "key", default="") or ""
        开关键 = 取任意(体, "开关键", "flagKey", "switchKey", default="") or ""
        票号 = 取任意(体, "票号", "ticketNo", "ticket", default="") or ""
        claimed_epoch = 取整数(体, "纪元", "载荷纪元", "epoch", default=None)
        claimed_hash = 取任意(体, "载荷哈希", "哈希", "hash", "payloadHash", default="")
        seen_epoch = 取整数(体, "所见纪元", "所见载荷纪元", "回读所见纪元", "seenEpoch", default=None)
        seen_hash = 取任意(
            体, "所见哈希", "所见载荷哈希", "回读所见哈希", "边缘哈希", "seenHash",
            default="",
        )
        if seen_epoch is None and claimed_epoch is not None and 票号:
            seen_epoch = claimed_epoch
        if not seen_hash and claimed_hash and 票号:
            seen_hash = claimed_hash

        ticket = None
        version = None
        if 票号:
            ticket = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (票号,)).fetchone()
            if not ticket:
                return {
                    "valid": False, "票号": 票号, "版本键": 版本键,
                    "纪元": claimed_epoch, "载荷纪元": claimed_epoch,
                    "载荷哈希": 规范化哈希值(claimed_hash),
                    "原因": "下发票不存在", "问题": ["下发票不存在"],
                }
            版本键 = 版本键 or ticket["版本键"]

        if not 版本键 and 开关键:
            row = conn.execute(
                "SELECT 版本键 FROM 开关版本 WHERE 开关键=? ORDER BY 入轨时 DESC LIMIT 1",
                (开关键,),
            ).fetchone()
            if row:
                版本键 = row["版本键"]

        if not 版本键 and claimed_hash:
            row = conn.execute(
                "SELECT 版本键 FROM 开关版本 WHERE 载荷哈希=? ORDER BY 入轨时 DESC LIMIT 1",
                (规范化哈希值(claimed_hash),),
            ).fetchone()
            if row:
                版本键 = row["版本键"]

        if 版本键:
            version = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (版本键,)).fetchone()
            if not version:
                return {
                    "valid": False, "票号": 票号, "版本键": 版本键,
                    "纪元": claimed_epoch, "载荷纪元": claimed_epoch,
                    "载荷哈希": 规范化哈希值(claimed_hash),
                    "原因": "版本未入轨", "问题": ["版本未入轨"],
                }

        if not version:
            if claimed_epoch is not None or claimed_hash or seen_epoch is not None or seen_hash:
                return {
                    "valid": False,
                    "verified": False,
                    "全量": False,
                    "版本键": 版本键,
                    "versionKey": 版本键,
                    "票号": 票号,
                    "ticketNo": 票号,
                    "纪元": claimed_epoch,
                    "epoch": claimed_epoch,
                    "载荷纪元": claimed_epoch,
                    "payloadEpoch": claimed_epoch,
                    "载荷哈希": 规范化哈希值(claimed_hash),
                    "payloadHash": 规范化哈希值(claimed_hash),
                    "所见纪元": seen_epoch,
                    "seenEpoch": seen_epoch,
                    "所见哈希": 规范化哈希值(seen_hash),
                    "seenHash": 规范化哈希值(seen_hash),
                    "原因": "缺少可核证的已入轨版本或下发票",
                    "reason": "missing version or ticket to certify",
                    "问题": ["缺少可核证的已入轨版本或下发票"],
                    "issues": ["missing version or ticket to certify"],
                }
            
            return 全量核证(conn)

        cur_epoch = 版本纪元(version)
        cur_hash = 版本哈希(version)
        stored_hash = 规范化哈希值(version["载荷哈希"] or "")
        recomputed_hash = 计算载荷哈希(version["载荷"])
        问题: list[str] = []
        if stored_hash and not 哈希相等(stored_hash, recomputed_hash):
            问题.append("库内载荷哈希与载荷重算结果不一致")

        pin_epoch = 票钉纪元(ticket) if ticket else None
        pin_hash = 票钉哈希(ticket) if ticket else ""
        pin_current = True
        if ticket:
            pin_current, pin_reason, _, _ = 票钉当前(conn, ticket, version)
            if not pin_current:
                问题.append(pin_reason)
            if ticket["状态"] in ("已作废", "已失效", "已回滚"):
                问题.append(f"票状态为{ticket['状态']}")

        
        claim_matches_current = True
        if not ticket and claimed_epoch is not None and claimed_epoch != cur_epoch:
            claim_matches_current = False
            问题.append("声明纪元不是当前纪元")
        if not ticket and claimed_hash and not 哈希相等(claimed_hash, cur_hash):
            claim_matches_current = False
            问题.append("声明载荷哈希不是当前哈希")

        observed_ok = True
        stale_seen = False
        norm_seen_hash = 规范化哈希值(seen_hash)
        if seen_epoch is not None:
            compare_to = pin_epoch if ticket else cur_epoch
            if seen_epoch != compare_to:
                observed_ok = False
                if seen_epoch < compare_to:
                    stale_seen = True
                    问题.append("所见纪元落后于同票钉纪元")
                else:
                    问题.append("所见纪元与同票钉纪元不一致")
        if norm_seen_hash:
            compare_hash = pin_hash if ticket else cur_hash
            if not 哈希相等(norm_seen_hash, compare_hash):
                observed_ok = False
                
                old_hit = conn.execute(
                    "SELECT 载荷纪元 FROM 载荷纪元史 WHERE 版本键=? AND 载荷哈希=? ORDER BY 载荷纪元 DESC LIMIT 1",
                    (版本键, norm_seen_hash),
                ).fetchone()
                old_pin_hit = conn.execute(
                    "SELECT 旧纪元 FROM 作废旧钉 WHERE 版本键=? AND 旧哈希=? LIMIT 1",
                    (版本键, norm_seen_hash),
                ).fetchone()
                if old_hit or old_pin_hit or (ticket and seen_epoch is not None and seen_epoch < (pin_epoch or cur_epoch)):
                    stale_seen = True
                    问题.append("边缘所见为旧纪元载荷哈希")
                else:
                    问题.append("所见哈希与同票钉哈希不一致")

        valid = not 问题 and claim_matches_current and pin_current and observed_ok
        原因 = "；".join(问题)
        return {
            "valid": bool(valid),
            "verified": bool(valid),
            "版本键": 版本键,
            "versionKey": 版本键,
            "票号": 票号,
            "ticketNo": 票号,
            "开关键": version["开关键"],
            "flagKey": version["开关键"],
            
            "纪元": cur_epoch,
            "epoch": cur_epoch,
            "载荷纪元": cur_epoch,
            "payloadEpoch": cur_epoch,
            "当前纪元": cur_epoch,
            "当前载荷纪元": cur_epoch,
            "currentEpoch": cur_epoch,
            "载荷哈希": cur_hash,
            "payloadHash": cur_hash,
            "当前哈希": cur_hash,
            "当前载荷哈希": cur_hash,
            "currentHash": cur_hash,
            "重算载荷哈希": recomputed_hash,
            "存储载荷哈希": stored_hash,
            "钉纪元": pin_epoch,
            "下发钉纪元": pin_epoch,
            "钉载荷纪元": pin_epoch,
            "pinnedEpoch": pin_epoch,
            "钉哈希": pin_hash,
            "下发钉哈希": pin_hash,
            "钉载荷哈希": pin_hash,
            "pinnedHash": pin_hash,
            "所见纪元": seen_epoch,
            "所见载荷纪元": seen_epoch,
            "seenEpoch": seen_epoch,
            "声明纪元": claimed_epoch,
            "请求纪元": claimed_epoch,
            "提交纪元": claimed_epoch,
            "声明载荷哈希": 规范化哈希值(claimed_hash),
            "请求载荷哈希": 规范化哈希值(claimed_hash),
            "所见哈希": norm_seen_hash,
            "所见载荷哈希": norm_seen_hash,
            "回读所见哈希": norm_seen_hash,
            "seenHash": norm_seen_hash,
            "旧纪元": stale_seen,
            "stale": stale_seen,
            "staleEpoch": stale_seen,
            "纪元差": (cur_epoch - (seen_epoch if seen_epoch is not None else pin_epoch or cur_epoch)),
            "epochDelta": (cur_epoch - (seen_epoch if seen_epoch is not None else pin_epoch or cur_epoch)),
            "票状态": ticket["状态"] if ticket else "",
            "ticketStatus": ticket["状态"] if ticket else "",
            "同票": bool(ticket),
            "原因": 原因,
            "reason": 原因,
            "问题": 问题,
            "issues": 问题,
        }
    finally:
        conn.close()


def 全量核证(conn=None) -> dict:
    own = conn is None
    conn = conn or 连接()
    try:
        版本项 = []
        all_valid = True
        for v in conn.execute("SELECT * FROM 开关版本 ORDER BY 版本键"):
            recomputed = 计算载荷哈希(v["载荷"])
            stored = 版本哈希(v)
            valid = (not v["载荷哈希"] or 哈希相等(stored, recomputed)) and 版本纪元(v) >= 1
            all_valid &= valid
            版本项.append({
                "类型": "开关版本",
                "版本键": v["版本键"],
                "versionKey": v["版本键"],
                "开关键": v["开关键"],
                "flagKey": v["开关键"],
                "纪元": 版本纪元(v),
                "epoch": 版本纪元(v),
                "载荷纪元": 版本纪元(v),
                "payloadEpoch": 版本纪元(v),
                "载荷哈希": stored or recomputed,
                "payloadHash": stored or recomputed,
                "valid": bool(valid),
            })
        票项 = []
        for t in conn.execute("SELECT * FROM 下发票 ORDER BY 票号"):
            current, reason, epoch, h = 票钉当前(conn, t)
            
            if t["状态"] in ("已作废", "已回滚", "已失效"):
                valid = True
                reason = ""
            else:
                valid = current and t["状态"] in ("已下发", "灰度中", "回滚中")
            all_valid &= valid
            票项.append({
                "类型": "下发票",
                "票号": t["票号"],
                "ticketNo": t["票号"],
                "版本键": t["版本键"],
                "versionKey": t["版本键"],
                "纪元": epoch,
                "epoch": epoch,
                "载荷纪元": epoch,
                "payloadEpoch": epoch,
                "下发钉纪元": epoch,
                "pinnedEpoch": epoch,
                "载荷哈希": h,
                "payloadHash": h,
                "下发钉哈希": h,
                "pinnedHash": h,
                "状态": t["状态"],
                "status": t["状态"],
                "valid": bool(valid),
                "原因": reason,
                "reason": reason,
            })
        return {
            "valid": bool(all_valid),
            "verified": bool(all_valid),
            "纪元": None,
            "epoch": None,
            "载荷纪元": None,
            "payloadEpoch": None,
            "载荷哈希": "",
            "payloadHash": "",
            "全量": True,
            "版本核证": 版本项,
            "下发票核证": 票项,
            "items": [*版本项, *票项],
            "数量": len(版本项) + len(票项),
        }
    finally:
        if own:
            conn.close()


def 列作废旧钉(版本键: str = "") -> list[dict]:
    conn = 连接()
    try:
        if 版本键:
            rows = conn.execute(
                "SELECT * FROM 作废旧钉 WHERE 版本键=? ORDER BY 编号 DESC", (版本键,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM 作废旧钉 ORDER BY 编号 DESC LIMIT 200").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
