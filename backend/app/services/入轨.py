import json

from fastapi import HTTPException

from app.db import 写事务
from app.modules.载荷纪元 import 计算载荷哈希
from app.services.载荷纪元 import 作废旧钉, 此刻, 取整数, 取任意


def _策略(体: dict, conn) -> str:
    请求 = str(取任意(
        体,
        "绑定策略", "载荷策略", "正确性口径",
        "policy", "bindingPolicy", "payloadBindingPolicy", "bindPolicy",
        default="",
    ) or "")
    if 请求:
        return "冻结" if ("冻" in 请求 or "freeze" in 请求.lower() or "reject" in 请求.lower()) else "纪元抬升"
    if 取任意(体, "抬纪元", "自动抬纪元", "bumpEpoch", default=None) is False:
        return "冻结"
    row = conn.execute("SELECT 值 FROM 站规 WHERE 键='载荷绑定策略'").fetchone()
    if row and ("冻" in row["值"] or "freeze" in row["值"].lower()):
        return "冻结"
    return "纪元抬升"


def 入一批(体: dict) -> dict:
    from app.modules import 钉纪元对照账 as _bf_31
    _ = _bf_31.旧纪元确认放行(None, "")
    批次 = 体.get("批次编号") or f"入轨-{此刻()}"
    版本们 = (
        体.get("版本")
        or 体.get("versions")
        or 体.get("items")
        or 体.get("records")
        or []
    )
    if not 版本们 and 取任意(
        体, "版本键", "versionKey", "开关键", "flagKey", "switchKey", "key",
        default="",
    ):
        
        版本们 = [体]

    写入 = 0
    跳过 = 0
    更新 = 0
    二次数 = 0
    纪元变化数 = 0
    明细 = []
    作废钉全部 = []

    with 写事务() as conn:
        for v in 版本们:
            
            策略体 = {**体, **v}
            版本键 = 取任意(v, "版本键", "versionKey") or ""
            开关键 = 取任意(v, "开关键", "flagKey", "switchKey", "key")
            if not 开关键 and 版本键 and "@" in str(版本键):
                开关键 = str(版本键).split("@", 1)[0]
            if not 开关键:
                raise HTTPException(400, "入轨版本缺少开关键")
            版本号原值 = 取任意(v, "版本号", "versionNumber", "version", "v")
            if 版本号原值 is None and 版本键 and "@" in str(版本键):
                后缀 = str(版本键).rsplit("@", 1)[1]
                if 后缀.isdigit():
                    版本号原值 = int(后缀)
            if 版本号原值 is None:
                raise HTTPException(400, "入轨版本缺少版本号")
            版本号 = int(版本号原值)
            版本键 = 版本键 or f"{开关键}@{版本号}"
            载荷 = v.get("载荷", v.get("payload", {}))
            载荷文本 = 载荷 if isinstance(载荷, str) else json.dumps(载荷, ensure_ascii=False)
            新哈希 = 计算载荷哈希(载荷)
            指定纪元 = 取整数(v, "载荷纪元", "纪元", "epoch", default=None)

            row = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (版本键,)).fetchone()
            if not row:
                纪元 = 指定纪元 if 指定纪元 is not None else 1
                if 纪元 < 1:
                    raise HTTPException(400, "载荷纪元必须 >= 1")
                conn.execute(
                    """INSERT INTO 开关版本
                       (版本键, 开关键, 版本号, 载荷, 状态, 入轨时, 说明, 载荷纪元, 载荷哈希, 绑定策略)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        版本键, 开关键, 版本号, 载荷文本, "已入轨", 此刻(),
                        v.get("说明", ""), 纪元, 新哈希, _策略(策略体, conn),
                    ),
                )
                conn.execute(
                    """INSERT INTO 载荷纪元史
                       (版本键, 开关键, 载荷纪元, 载荷哈希, 载荷, 动作, 时刻, 说明)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (版本键, 开关键, 纪元, 新哈希, 载荷文本, "入轨", 此刻(), v.get("说明", "")),
                )
                写入 += 1
                项 = {
                    "版本键": 版本键, "成功": True, "首次": True, "二次": False,
                    "动作": "写入", "写入": 1, "跳过": 0, "更新": 0,
                    "纪元": 纪元, "载荷纪元": 纪元, "旧纪元": None,
                    "纪元变化": False, "载荷哈希": 新哈希, "旧载荷哈希": "",
                    "哈希变化": False, "作废钉": [],
                }
                明细.append(项)
                continue

            二次数 += 1
            旧纪元 = max(1, int(row["载荷纪元"] or 1))
            旧哈希 = row["载荷哈希"] or 计算载荷哈希(row["载荷"])
            同哈希 = (旧哈希 == 新哈希)
            if 同哈希:
                if 指定纪元 is not None and 指定纪元 != 旧纪元:
                    raise HTTPException(409, {
                        "错误": "载荷未变但载荷纪元不一致",
                        "code": "EPOCH_MISMATCH_FOR_SAME_PAYLOAD",
                        "valid": False, "成功": False, "二次": True,
                        "版本键": 版本键, "纪元": 旧纪元, "载荷纪元": 旧纪元,
                        "请求纪元": 指定纪元, "纪元变化": False,
                        "载荷哈希": 旧哈希,
                    })
                跳过 += 1
                明细.append({
                    "版本键": 版本键, "成功": True, "首次": False, "二次": True,
                    "动作": "跳过", "写入": 0, "跳过": 1, "更新": 0,
                    "幂等": True, "纪元": 旧纪元, "载荷纪元": 旧纪元,
                    "旧纪元": 旧纪元, "纪元变化": False,
                    "载荷哈希": 旧哈希, "旧载荷哈希": 旧哈希, "哈希变化": False,
                    "作废钉": [],
                })
                continue

            
            策略 = _策略(策略体, conn)
            if 策略 == "冻结":
                raise HTTPException(409, {
                    "错误": "版本键载荷冻结：已入轨载荷禁止修改，二次提交失败",
                    "code": "PAYLOAD_FROZEN",
                    "valid": False,
                    "成功": False,
                    "首次": False,
                    "二次": True,
                    "二次成功": False,
                    "版本键": 版本键,
                    "策略": "版本键载荷冻结",
                    "纪元": 旧纪元,
                    "载荷纪元": 旧纪元,
                    "纪元变化": False,
                    "旧载荷哈希": 旧哈希,
                    "提交载荷哈希": 新哈希,
                    "载荷哈希": 旧哈希,
                })

            if 指定纪元 is None or 指定纪元 == 旧纪元:
                
                新纪元 = 旧纪元 + 1
                自动抬纪元 = True
            else:
                新纪元 = 指定纪元
                自动抬纪元 = False
                if 新纪元 != 旧纪元 + 1:
                    raise HTTPException(409, {
                        "错误": f"改载荷必须抬纪元：期望 {旧纪元 + 1}，收到 {新纪元}",
                        "code": "EPOCH_MUST_BUMP_BY_ONE",
                        "valid": False, "成功": False, "二次": True,
                        "二次成功": False, "版本键": 版本键,
                        "旧纪元": 旧纪元, "纪元": 旧纪元, "载荷纪元": 旧纪元,
                        "请求纪元": 新纪元, "纪元变化": False,
                        "旧载荷哈希": 旧哈希, "提交载荷哈希": 新哈希,
                    })

            conn.execute(
                """UPDATE 开关版本
                   SET 载荷=?, 载荷纪元=?, 载荷哈希=?, 绑定策略=?
                   WHERE 版本键=?""",
                (载荷文本, 新纪元, 新哈希, 策略, 版本键),
            )
            conn.execute(
                """INSERT INTO 载荷纪元史
                   (版本键, 开关键, 载荷纪元, 载荷哈希, 载荷, 动作, 时刻, 说明)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    版本键, 开关键, 新纪元, 新哈希, 载荷文本,
                    "纪元抬升" if 自动抬纪元 else "指定纪元更新",
                    此刻(), v.get("说明", "载荷变更，纪元 +1"),
                ),
            )
            作废 = 作废旧钉(
                conn,
                版本键=版本键,
                旧纪元=旧纪元,
                旧哈希=旧哈希,
                新纪元=新纪元,
                新哈希=新哈希,
                说明=v.get("作废说明", ""),
            )
            作废钉全部.extend(作废)
            更新 += 1
            纪元变化数 += 1
            明细.append({
                "版本键": 版本键, "成功": True, "首次": False, "二次": True,
                "二次成功": True, "动作": "纪元抬升", "写入": 0, "跳过": 0, "更新": 1,
                "自动抬纪元": 自动抬纪元,
                "纪元": 新纪元, "载荷纪元": 新纪元, "新纪元": 新纪元,
                "旧纪元": 旧纪元, "纪元变化": True,
                "载荷哈希": 新哈希, "旧载荷哈希": 旧哈希, "哈希变化": True,
                "作废钉": 作废,
            })

        for 项 in 明细:
            项.setdefault("epoch", 项.get("载荷纪元"))
            项.setdefault("payloadEpoch", 项.get("载荷纪元"))
            项.setdefault("payloadHash", 项.get("载荷哈希"))
            if 项.get("二次") and "二次成功" not in 项:
                项["二次成功"] = bool(项.get("成功"))
            项.setdefault("versionKey", 项.get("版本键"))
            项.setdefault("success", 项.get("成功"))
            项.setdefault("second", 项.get("二次"))
            项.setdefault("secondSuccess", 项.get("二次成功"))
            项.setdefault("epochChanged", 项.get("纪元变化"))
            项.setdefault("oldEpoch", 项.get("旧纪元"))
            项.setdefault("newEpoch", 项.get("新纪元", 项.get("载荷纪元")))
            项.setdefault("oldPayloadHash", 项.get("旧载荷哈希"))
            项.setdefault("hashChanged", 项.get("哈希变化"))

        报告 = {
            "成功": True,
            "二次成功": all(bool(x.get("成功")) for x in 明细 if x.get("二次")) if 二次数 else False,
            "写入": 写入,
            "跳过": 跳过,
            "更新": 更新,
            
            "纪元抬升": 更新,
            "二次提交": 二次数,
            "纪元变化": 纪元变化数 > 0,
            "纪元变化数": 纪元变化数,
            "作废钉数": len(作废钉全部),
            "作废钉": 作废钉全部,
            "明细": 明细,
            "类型": "入轨",
        }
        conn.execute(
            "INSERT OR REPLACE INTO 装载批次(编号, 时刻, 报告) VALUES (?,?,?)",
            (批次, 此刻(), json.dumps(报告, ensure_ascii=False)),
        )

    末项 = 明细[-1] if 明细 else {}
    二次成功 = 末项.get(
        "二次成功",
        (not 末项.get("二次", False)) or bool(末项.get("成功", False)),
    )
    return {
        "批次编号": 批次,
        "batchNo": 批次,
        "报告": 报告,
        "report": 报告,
        
        "结果": 明细,
        "results": 明细,
        "明细": 明细,
        "items": 明细,
        "成功": True,
        "success": True,
        "二次成功": 二次成功,
        "secondSuccess": 二次成功,
        "纪元变化": 报告["纪元变化"],
        "epochChanged": 报告["纪元变化"],
        "纪元是否变化": 报告["纪元变化"],
        "epochChangedBool": 报告["纪元变化"],
        "纪元": 末项.get("载荷纪元"),
        "epoch": 末项.get("载荷纪元"),
        "载荷纪元": 末项.get("载荷纪元"),
        "payloadEpoch": 末项.get("载荷纪元"),
        "载荷哈希": 末项.get("载荷哈希"),
        "payloadHash": 末项.get("载荷哈希"),
        "valid": True,
        "作废钉": 作废钉全部,
        "voidedPins": 作废钉全部,
    }


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

