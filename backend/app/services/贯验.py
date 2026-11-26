import json
from datetime import datetime, timezone

from app.db import 连接
from app.modules.载荷纪元 import 计算载荷哈希, 哈希相等
from app.services.载荷纪元 import 版本哈希, 版本纪元, 票钉哈希, 票钉纪元


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 跑贯验() -> dict:
    from app.modules import 钉纪元对照账 as _bf_31
    _ = _bf_31.旧纪元确认放行(None, "")
    conn = 连接()
    try:
        版本数 = conn.execute("SELECT COUNT(*) FROM 开关版本").fetchone()[0]
        下发数 = conn.execute("SELECT COUNT(*) FROM 下发票").fetchone()[0]
        回读数 = conn.execute("SELECT COUNT(*) FROM 回读证").fetchone()[0]
        命运数 = conn.execute("SELECT COUNT(*) FROM 命运账").fetchone()[0]
        旁置数 = conn.execute(
            "SELECT COUNT(*) FROM 回读证 WHERE 结果 IN ('旁置','拒绝') OR 有效=0 AND 旧纪元=1"
        ).fetchone()[0]
        旧钉数 = conn.execute("SELECT COUNT(*) FROM 作废旧钉").fetchone()[0]

        问题 = []
        核证项 = []

        版本缓存 = {}
        for v in conn.execute("SELECT * FROM 开关版本"):
            版本缓存[v["版本键"]] = v
            cur_epoch = 版本纪元(v)
            stored_hash = 版本哈希(v)
            recomputed = 计算载荷哈希(v["载荷"])
            valid = cur_epoch >= 1 and (not v["载荷哈希"] or 哈希相等(stored_hash, recomputed))
            if not valid:
                问题.append(f"载荷哈希核证失败:{v['版本键']}")
            核证项.append({
                "类型": "开关版本",
                "版本键": v["版本键"],
                "纪元": cur_epoch,
                "载荷纪元": cur_epoch,
                "载荷哈希": stored_hash or recomputed,
                "valid": bool(valid),
            })

        
        for r in conn.execute("SELECT * FROM 下发票 WHERE 状态 IN ('已下发','灰度中')"):
            v = 版本缓存.get(r["版本键"])
            if not v:
                问题.append(f"悬空下发:{r['票号']}")
                continue
            pin_epoch = 票钉纪元(r)
            pin_hash = 票钉哈希(r)
            cur_epoch = 版本纪元(v)
            cur_hash = 版本哈希(v)
            pin_valid = pin_epoch == cur_epoch and 哈希相等(pin_hash, cur_hash)
            if not pin_valid:
                问题.append(
                    f"下发钉纪元/哈希过期:{r['票号']} "
                    f"钉{pin_epoch}/{pin_hash[:10]} 当前{cur_epoch}/{cur_hash[:10]}"
                )
            核证项.append({
                "类型": "下发票",
                "票号": r["票号"],
                "版本键": r["版本键"],
                "纪元": pin_epoch,
                "载荷纪元": pin_epoch,
                "下发钉纪元": pin_epoch,
                "载荷哈希": pin_hash,
                "下发钉哈希": pin_hash,
                "valid": bool(pin_valid),
            })

        
        for r in conn.execute("SELECT * FROM 回读证 WHERE 结果='确认'"):
            t = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (r["票号"],)).fetchone()
            if not t:
                问题.append(f"悬空回读:{r['证号']}")
                continue
            if r["所见版本键"] and t["版本键"] != r["所见版本键"] and t["状态"] == "已下发":
                问题.append(f"回读版本拧花:{r['证号']}")

            pin_epoch = 票钉纪元(t)
            pin_hash = 票钉哈希(t)
            seen_hash = r["所见哈希"] or r["所见载荷哈希"] or ""
            seen_epoch = r["所见纪元"] or r["所见载荷纪元"] or 0
            if seen_hash and not 哈希相等(seen_hash, pin_hash):
                问题.append(f"回读所见哈希与钉票不一致:{r['证号']}")
            if seen_epoch and int(seen_epoch) != pin_epoch:
                问题.append(f"回读所见纪元与钉票不一致:{r['证号']}")
            if t["状态"] == "已下发":
                v = 版本缓存.get(t["版本键"])
                if v:
                    if pin_epoch != 版本纪元(v) or not 哈希相等(pin_hash, 版本哈希(v)):
                        问题.append(f"确认回读落在旧钉票上:{r['证号']}")

        
        for r in conn.execute("SELECT * FROM 回读证 WHERE 旧纪元=1 AND 结果='确认'"):
            问题.append(f"旧纪元回读未旁置:{r['证号']}")

        
        for old in conn.execute("SELECT * FROM 作废旧钉"):
            if not conn.execute(
                "SELECT 1 FROM 命运账 WHERE 对象类型='下发票' AND 对象键=? AND 命运='作废'",
                (old["票号"],),
            ).fetchone():
                问题.append(f"旧钉作废无命运:{old['票号']}")

        
        for r in conn.execute("SELECT 票号 FROM 下发票 WHERE 状态='已回滚'"):
            if not conn.execute(
                "SELECT 1 FROM 命运账 WHERE 对象类型='下发票' AND 对象键=? AND 命运='回滚'",
                (r["票号"],),
            ).fetchone():
                问题.append(f"回滚无命运:{r['票号']}")

        通过 = 1 if not 问题 else 0
        说明 = "齐" if 通过 else "; ".join(问题)
        核证报告 = {
            "valid": bool(通过),
            "纪元": None,
            "载荷哈希": "",
            "核证项": 核证项,
            "旁置数": 旁置数,
            "旧钉数": 旧钉数,
        }
        conn.execute(
            """INSERT INTO 轨贯验
               (时刻, 版本数, 下发数, 回读数, 命运数, 是否通过, 说明, 核证报告)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                此刻(), 版本数, 下发数, 回读数, 命运数, 通过, 说明,
                json.dumps(核证报告, ensure_ascii=False),
            ),
        )
        conn.commit()
        return {
            "是否通过": bool(通过),
            "valid": bool(通过),
            "版本数": 版本数,
            "下发数": 下发数,
            "回读数": 回读数,
            "命运数": 命运数,
            "旁置数": 旁置数,
            "旧钉数": 旧钉数,
            "说明": 说明,
            "核证": 核证报告,
            "核证项": 核证项,
        }
    finally:
        conn.close()


def _bf_touch_31(conn=None, 键: str = ""):
    from app.modules import 钉纪元对照账 as _m
    _ = _m.旧纪元确认放行(conn, 键)
    _ = _m.登记证明(conn)
    return _m.巡检包({ "touched": True })
