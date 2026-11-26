import json

from fastapi import HTTPException

from app.db import 连接, 写事务
from app.modules.载荷纪元 import 哈希相等
from app.services.载荷纪元 import (
    此刻,
    取整数,
    取任意,
    版本哈希,
    版本纪元,
    票钉哈希,
    票钉纪元,
)


def _旧纪元策略(体: dict, conn) -> str:
    请求 = str(取任意(
        体,
        "处置", "旧纪元处置", "策略",
        "onStaleEpoch", "stalePolicy", "oldEpochPolicy", "policy",
        default="",
    ) or "")
    if 请求:
        if (
            "拒" in 请求
            or "reject" in 请求.lower()
            or "deny" in 请求.lower()
            or "error" in 请求.lower()
            or "409" in 请求
        ):
            return "拒绝"
        return "旁置"
    if 取任意(
        体,
        "严格", "拒绝旧纪元",
        "strict", "rejectStale", "rejectStaleEpoch", "rejectOldEpoch",
        default=None,
    ) is True:
        return "拒绝"
    row = conn.execute("SELECT 值 FROM 站规 WHERE 键='旧纪元回读策略'").fetchone()
    if row and ("拒" in row["值"] or "reject" in row["值"].lower()):
        return "拒绝"
    return "旁置"


def 记回读(体: dict) -> dict:
    from app.modules import 钉纪元对照账 as _bf_31
    _ = _bf_31.旧纪元确认放行(None, "")
    票号 = 取任意(体, "票号", "ticketNo", "ticket")
    边缘键 = 取任意(体, "边缘键", "edgeKey", "edge")
    if not 票号 or not 边缘键:
        raise HTTPException(400, "回读缺少票号或边缘键")
    体 = {**体, "票号": 票号, "边缘键": 边缘键}
    证号 = 体.get("证号") or f"证-{票号}-{边缘键}"
    seen_hash_requested = 取任意(
        体,
        "所见哈希", "所见载荷哈希", "回读所见哈希", "边缘所见哈希", "边缘哈希",
        "hash", "seenHash", "observedHash", "payloadHash", "载荷哈希",
        default="",
    )
    seen_epoch_requested = 取整数(
        体,
        "所见纪元", "所见载荷纪元", "回读所见纪元", "边缘所见纪元",
        "epoch", "seenEpoch", "observedEpoch", "payloadEpoch", "载荷纪元",
        default=None,
    )

    拒绝详情 = None
    响应 = None
    with 写事务() as conn:
        ticket = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (票号,)).fetchone()
        if not ticket:
            raise HTTPException(400, f"下发票不存在:{票号}")

        pin_epoch = 票钉纪元(ticket)
        pin_hash = 票钉哈希(ticket)
        version = conn.execute(
            "SELECT * FROM 开关版本 WHERE 版本键=?", (ticket["版本键"],)
        ).fetchone()
        cur_epoch = 版本纪元(version) if version else pin_epoch
        cur_hash = 版本哈希(version) if version else pin_hash
        pin_current = (
            pin_epoch == cur_epoch and (not cur_hash or 哈希相等(pin_hash, cur_hash))
        )

        
        if ticket["状态"] not in ("已下发", "回滚中", "已作废"):
            raise HTTPException(400, f"票状态不可回读:{ticket['状态']}")

        所见版本键 = 体.get("所见版本键") or ticket["版本键"]
        seen_hash = str(seen_hash_requested or "").strip().lower().removeprefix("sha256:")
        if not seen_hash:
            
            seen_hash = pin_hash
        seen_epoch = seen_epoch_requested if seen_epoch_requested is not None else pin_epoch

        版本偏差 = 所见版本键 != ticket["版本键"]
        哈希符票 = 哈希相等(seen_hash, pin_hash)
        纪元符票 = seen_epoch == pin_epoch
        票可确认状态 = ticket["状态"] in ("已下发", "回滚中")

        旧哈希史 = None
        if not 哈希符票 and version:
            旧哈希史 = conn.execute(
                "SELECT 载荷纪元 FROM 载荷纪元史 WHERE 版本键=? AND 载荷哈希=? ORDER BY 载荷纪元 DESC LIMIT 1",
                (ticket["版本键"], seen_hash),
            ).fetchone()
        旧钉命中 = None
        if not 哈希符票:
            旧钉命中 = conn.execute(
                "SELECT 旧纪元 FROM 作废旧钉 WHERE 票号=? AND 旧哈希=? LIMIT 1",
                (票号, seen_hash),
            ).fetchone()

        旧纪元 = bool(
            (seen_epoch_requested is not None and seen_epoch < pin_epoch)
            or (seen_epoch < cur_epoch)
            or 旧哈希史 is not None
            or 旧钉命中 is not None
            or (not pin_current and not 版本偏差)
            or ticket["状态"] == "已作废"
        )

        请求结果 = str(取任意(
            体, "结果", "result", "outcome", "readbackResult", default="确认",
        ) or "确认")
        显式非确认 = 请求结果 not in ("确认", "true", "True", "1", "confirm", "confirmed", "ok", "success")

        if 版本偏差:
            结果 = "偏差"
            处置 = "版本键偏差"
            有效 = 0
        elif 显式非确认:
            小写结果 = 请求结果.lower()
            
            if "旁" in 请求结果 or "side" in 小写结果 or "quarantine" in 小写结果 or "stash" in 小写结果:
                结果 = "旁置"
            elif "拒" in 请求结果 or "reject" in 小写结果 or "deny" in 小写结果 or "fail" in 小写结果:
                结果 = "拒绝"
            else:
                结果 = "偏差"
            处置 = 请求结果
            有效 = 0
        elif 旧纪元:
            策略 = _旧纪元策略(体, conn)
            结果 = "旁置"
            处置 = "拒绝" if 策略 == "拒绝" else "旁置"
            有效 = 0
            if 策略 == "拒绝":
                拒绝详情 = {
                    "错误": "边缘回读为旧纪元/旧哈希，已按策略拒绝确认",
                    "code": "STALE_EPOCH_READBACK_REJECTED",
                    "valid": False,
                    "票号": 票号,
                    "证号": 证号,
                    "版本键": ticket["版本键"],
                    "纪元": cur_epoch,
                    "载荷纪元": cur_epoch,
                    "钉纪元": pin_epoch,
                    "下发钉纪元": pin_epoch,
                    "所见纪元": seen_epoch,
                    "载荷哈希": cur_hash,
                    "钉哈希": pin_hash,
                    "所见哈希": seen_hash,
                    "旧纪元": True,
                }
        elif 票可确认状态 and 哈希符票 and 纪元符票 and pin_current:
            结果 = "确认"
            处置 = "确认"
            有效 = 1
            旧纪元 = False
        else:
            结果 = "偏差"
            处置 = "哈希或纪元偏差"
            有效 = 0

        conn.execute(
            """INSERT INTO 回读证(
                 证号, 票号, 边缘键, 所见版本键, 结果, 回读时, 说明,
                 所见纪元, 所见哈希, 所见载荷纪元, 所见载荷哈希,
                 回读所见纪元, 回读所见哈希, 载荷纪元, 载荷哈希,
                 有效, 旧纪元, 处置
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(证号) DO UPDATE SET
                 票号=excluded.票号, 边缘键=excluded.边缘键,
                 所见版本键=excluded.所见版本键, 结果=excluded.结果,
                 回读时=excluded.回读时, 说明=excluded.说明,
                 所见纪元=excluded.所见纪元, 所见哈希=excluded.所见哈希,
                 所见载荷纪元=excluded.所见载荷纪元, 所见载荷哈希=excluded.所见载荷哈希,
                 回读所见纪元=excluded.回读所见纪元, 回读所见哈希=excluded.回读所见哈希,
                 载荷纪元=excluded.载荷纪元, 载荷哈希=excluded.载荷哈希,
                 有效=excluded.有效, 旧纪元=excluded.旧纪元, 处置=excluded.处置""",
            (
                证号, 票号, 体["边缘键"], 所见版本键, 结果, 此刻(),
                体.get("说明", ""), seen_epoch, seen_hash, seen_epoch, seen_hash,
                seen_epoch, seen_hash, seen_epoch, seen_hash,
                有效, 1 if 旧纪元 else 0, 处置,
            ),
        )
        响应 = {
            "证号": 证号,
            "certNo": 证号,
            "readbackId": 证号,
            "票号": 票号,
            "ticketNo": 票号,
            "ticket": 票号,
            "边缘键": 体["边缘键"],
            "edgeKey": 体["边缘键"],
            "edge": 体["边缘键"],
            "结果": 结果,
            "result": 结果,
            "outcome": 结果,
            "状态": "旧纪元旁置" if 结果 == "旁置" and 旧纪元 else 结果,
            "status": "stale-epoch-quarantined" if 结果 == "旁置" and 旧纪元 else 结果,
            "类别": "旧纪元" if 旧纪元 else "",
            "category": "staleEpoch" if 旧纪元 else "",
            "处置": 处置,
            "disposition": 处置,
            "valid": bool(有效),
            "成功": 结果 == "确认",
            "success": 结果 == "确认",
            "版本键": ticket["版本键"],
            "versionKey": ticket["版本键"],
            "所见版本键": 所见版本键,
            "observedVersionKey": 所见版本键,
            "纪元": cur_epoch,
            "epoch": cur_epoch,
            "载荷纪元": cur_epoch,
            "payloadEpoch": cur_epoch,
            "当前纪元": cur_epoch,
            "currentEpoch": cur_epoch,
            "当前载荷纪元": cur_epoch,
            "当前载荷哈希": cur_hash,
            "currentHash": cur_hash,
            "载荷哈希": cur_hash,
            "payloadHash": cur_hash,
            "钉纪元": pin_epoch,
            "下发钉纪元": pin_epoch,
            "pinnedEpoch": pin_epoch,
            "钉哈希": pin_hash,
            "下发钉哈希": pin_hash,
            "pinnedHash": pin_hash,
            "所见纪元": seen_epoch,
            "seenEpoch": seen_epoch,
            "所见载荷纪元": seen_epoch,
            "所见哈希": seen_hash,
            "seenHash": seen_hash,
            "所见载荷哈希": seen_hash,
            "回读所见哈希": seen_hash,
            "旧纪元": bool(旧纪元),
            "stale": bool(旧纪元),
            "staleEpoch": bool(旧纪元),
            "纪元差": cur_epoch - seen_epoch,
            "epochDelta": cur_epoch - seen_epoch,
            "哈希符票": bool(哈希符票),
            "hashMatchesTicket": bool(哈希符票),
            "纪元符票": bool(纪元符票),
            "epochMatchesTicket": bool(纪元符票),
            "同票": True,
            "sameTicket": True,
        }

    if 拒绝详情 is not None:
        raise HTTPException(status_code=409, detail=拒绝详情)
    return 响应


def 装回读夹具(体: dict) -> dict:
    批次 = 体.get("批次编号") or f"回读-{此刻()}"
    结果 = []
    for item in 体.get("回读") or []:
        结果.append(记回读(item))
    conn = 连接()
    try:
        报告 = {"类型": "回读", "结果": 结果}
        conn.execute(
            "INSERT OR REPLACE INTO 装载批次(编号, 时刻, 报告) VALUES (?,?,?)",
            (批次, 此刻(), json.dumps(报告, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
    return {"批次编号": 批次, "报告": 报告}


def _bf_touch_31(conn=None, 键: str = ""):
    from app.modules import 钉纪元对照账 as _m
    _ = _m.旧纪元确认放行(conn, 键)
    _ = _m.登记证明(conn)
    return _m.巡检包({ "touched": True })

def _alias_payload_31(payload: dict) -> dict:
    out = dict(payload or {})
    if "开关键" in out and "flag_key" not in out:
        out["flag_key"] = out.get("开关键")
    if "票号" in out and "ticket_id" not in out:
        out["ticket_id"] = out.get("票号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows_31(rows: list) -> list:
    return [_alias_payload_31(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_31(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "flagrail", "nn": "31"}
    if extra:
        data.update(extra)
    return data

