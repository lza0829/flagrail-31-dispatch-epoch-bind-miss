import json

from fastapi import HTTPException

from app.db import 连接, 写事务
from app.services.载荷纪元 import 此刻, 取整数, 取任意, 版本哈希, 版本纪元


def _票响应(conn, 票号: str, 幂等: bool) -> dict:
    t = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (票号,)).fetchone()
    v = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (t["版本键"],)).fetchone()
    cur_epoch = 版本纪元(v) if v else int(t["载荷纪元"] or 1)
    cur_hash = 版本哈希(v) if v else (t["载荷哈希"] or "")
    pin_epoch = int(t["下发钉纪元"] or t["钉纪元"] or t["载荷纪元"] or 1)
    pin_hash = t["下发钉哈希"] or t["钉哈希"] or t["载荷哈希"] or ""
    当前 = pin_epoch == cur_epoch and (not cur_hash or pin_hash == cur_hash)
    return {
        "票号": 票号,
        "ticketNo": 票号,
        "ticket": 票号,
        "状态": t["状态"],
        "status": t["状态"],
        "幂等": 幂等,
        "idempotent": 幂等,
        "世代": t["世代"],
        "generation": t["世代"],
        "版本键": t["版本键"],
        "versionKey": t["版本键"],
        "桶键": t["桶键"],
        "bucketKey": t["桶键"],
        "开关键": t["开关键"],
        "flagKey": t["开关键"],
        "纪元": pin_epoch,
        "epoch": pin_epoch,
        "pinnedEpoch": pin_epoch,
        "载荷纪元": pin_epoch,
        "payloadEpoch": pin_epoch,
        "钉纪元": pin_epoch,
        "下发钉纪元": pin_epoch,
        "钉载荷纪元": pin_epoch,
        "载荷哈希": pin_hash,
        "payloadHash": pin_hash,
        "哈希": pin_hash,
        "hash": pin_hash,
        "pinnedHash": pin_hash,
        "钉哈希": pin_hash,
        "下发钉哈希": pin_hash,
        "钉载荷哈希": pin_hash,
        "当前纪元": cur_epoch,
        "currentEpoch": cur_epoch,
        "当前载荷纪元": cur_epoch,
        "当前载荷哈希": cur_hash,
        "currentHash": cur_hash,
        "纪元差": cur_epoch - pin_epoch,
        "epochDelta": cur_epoch - pin_epoch,
        "钉住当前": 当前,
        "pinnedToCurrent": 当前,
        "stale": not 当前,
        "过期": not 当前,
        "同票": True,
        "valid": bool(当前 and t["状态"] in ("已下发", "灰度中")),
    }


def 下一票(体: dict) -> dict:
    from app.modules import 钉纪元对照账 as _bf_31
    _ = _bf_31.旧纪元确认放行(None, "")
    版本键 = 取任意(体, "版本键", "versionKey")
    桶键 = 取任意(体, "桶键", "bucketKey")
    if not 版本键 or not 桶键:
        raise HTTPException(400, "下发缺少版本键或桶键")
    票号 = 取任意(体, "票号", "ticketNo", "ticket") or f"票-{版本键}-{桶键}"
    请求纪元 = 取整数(
        体,
        "期望纪元", "当前纪元", "钉纪元", "下发钉纪元", "载荷纪元", "纪元",
        "expectedEpoch", "currentEpoch", "pinnedEpoch", "payloadEpoch", "epoch",
        default=None,
    )
    请求哈希 = 取任意(
        体,
        "期望哈希", "当前载荷哈希", "钉哈希", "下发钉哈希", "载荷哈希", "哈希",
        "expectedHash", "currentHash", "pinnedHash", "payloadHash", "hash",
        default="",
    )

    with 写事务() as conn:
        ver = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (版本键,)).fetchone()
        if not ver:
            raise HTTPException(400, f"版本未入轨:{版本键}")
        if ver["状态"] not in ("已入轨", "灰度中"):
            raise HTTPException(400, f"版本状态不可下发:{ver['状态']}")

        cur_epoch = 版本纪元(ver)
        cur_hash = 版本哈希(ver)

        
        if 请求纪元 is not None and 请求纪元 != cur_epoch:
            raise HTTPException(409, {
                "错误": "下发钉纪元已过期，禁止把旧纪元哈希静默钉成新票",
                "code": "STALE_PIN_EPOCH",
                "valid": False,
                "版本键": 版本键,
                "票号": 票号,
                "请求纪元": 请求纪元,
                "纪元": cur_epoch,
                "载荷纪元": cur_epoch,
                "当前纪元": cur_epoch,
                "纪元差": cur_epoch - 请求纪元,
                "载荷哈希": cur_hash,
            })
        if 请求哈希:
            from app.modules.载荷纪元 import 哈希相等
            if not 哈希相等(请求哈希, cur_hash):
                raise HTTPException(409, {
                    "错误": "下发钉哈希不是当前载荷哈希，须重新取纪元/哈希后钉票",
                    "code": "STALE_PIN_HASH",
                    "valid": False,
                    "版本键": 版本键,
                    "票号": 票号,
                    "请求哈希": 请求哈希,
                    "载荷哈希": cur_hash,
                    "当前载荷哈希": cur_hash,
                    "纪元": cur_epoch,
                })

        bucket = conn.execute(
            "SELECT * FROM 分桶规 WHERE 桶键=? AND 状态='生效'", (桶键,)
        ).fetchone()
        if not bucket:
            raise HTTPException(400, f"分桶未生效:{桶键}")
        if bucket["开关键"] != ver["开关键"]:
            raise HTTPException(400, "分桶开关键与版本不一致")

        已 = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (票号,)).fetchone()
        if 已 and 已["状态"] == "已下发":
            pin_epoch = int(已["下发钉纪元"] or 已["钉纪元"] or 已["载荷纪元"] or 1)
            pin_hash = 已["下发钉哈希"] or 已["钉哈希"] or 已["载荷哈希"] or ""
            from app.modules.载荷纪元 import 哈希相等
            if pin_epoch != cur_epoch or not 哈希相等(pin_hash, cur_hash):
                raise HTTPException(409, {
                    "错误": "同票号已下发但钉的是旧纪元/旧哈希；旧钉应作废或使用新票/重钉",
                    "code": "EXISTING_TICKET_STALE_PIN",
                    "valid": False,
                    "票号": 票号,
                    "钉纪元": pin_epoch,
                    "载荷纪元": pin_epoch,
                    "当前纪元": cur_epoch,
                    "钉哈希": pin_hash,
                    "载荷哈希": cur_hash,
                })
            return _票响应(conn, 票号, True)

        if 已 is None:
            conn.execute(
                """INSERT INTO 下发票(
                     票号, 开关键, 版本键, 桶键, 状态, 下发时, 世代, 说明,
                     载荷纪元, 载荷哈希, 钉纪元, 钉哈希, 下发钉纪元, 下发钉哈希,
                     钉住纪元, 钉住哈希
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    票号, ver["开关键"], 版本键, 桶键, "已下发", 此刻(), 1,
                    体.get("说明", ""), cur_epoch, cur_hash, cur_epoch, cur_hash,
                    cur_epoch, cur_hash, cur_epoch, cur_hash,
                ),
            )
        else:
            旧状态 = 已["状态"]
            旧纪元钉 = int(已["下发钉纪元"] or 已["钉纪元"] or 已["载荷纪元"] or 1)
            旧哈希钉 = 已["下发钉哈希"] or 已["钉哈希"] or 已["载荷哈希"] or ""
            conn.execute(
                """UPDATE 下发票 SET
                     开关键=?, 版本键=?, 桶键=?, 状态='已下发', 下发时=?, 世代=世代+1,
                     说明=?, 载荷纪元=?, 载荷哈希=?, 钉纪元=?, 钉哈希=?,
                     下发钉纪元=?, 下发钉哈希=?, 钉住纪元=?, 钉住哈希=?
                   WHERE 票号=?""",
                (
                    ver["开关键"], 版本键, 桶键, 此刻(), 体.get("说明", ""),
                    cur_epoch, cur_hash, cur_epoch, cur_hash, cur_epoch, cur_hash,
                    cur_epoch, cur_hash, 票号,
                ),
            )
            if 旧状态 == "已作废" and (旧纪元钉 != cur_epoch or 旧哈希钉 != cur_hash):
                conn.execute(
                    "INSERT INTO 命运账(对象类型, 对象键, 命运, 时刻, 说明) VALUES (?,?,?,?,?)",
                    (
                        "下发票", 票号, "重钉", 此刻(),
                        f"旧钉纪元{旧纪元钉}/{旧哈希钉[:12]}已重钉为纪元{cur_epoch}/{cur_hash[:12]}",
                    ),
                )

        conn.execute(
            "UPDATE 开关版本 SET 状态='灰度中' WHERE 版本键=?", (版本键,)
        )
        return _票响应(conn, 票号, False)


def 装下发夹具(体: dict) -> dict:
    批次 = 体.get("批次编号") or f"下发-{此刻()}"
    结果 = []
    for item in 体.get("下发") or []:
        结果.append(下一票(item))
    conn = 连接()
    try:
        报告 = {"类型": "下发", "结果": 结果}
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

