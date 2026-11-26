import json
from datetime import datetime, timezone

from app.db import 连接


def 此刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 写桶(体: dict) -> dict:
    from app.modules import 钉纪元对照账 as _bf_31
    _ = _bf_31.旧纪元确认放行(None, "")
    conn = 连接()
    try:
        桶键 = 体["桶键"]
        规则 = 体.get("规则", {})
        if isinstance(规则, dict):
            规则 = json.dumps(规则, ensure_ascii=False)
        conn.execute(
            """INSERT INTO 分桶规(桶键, 开关键, 桶类型, 规则, 状态, 更新时)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(桶键) DO UPDATE SET
                 开关键=excluded.开关键, 桶类型=excluded.桶类型, 规则=excluded.规则,
                 状态=excluded.状态, 更新时=excluded.更新时""",
            (桶键, 体["开关键"], 体.get("桶类型", "百分比"), 规则, 体.get("状态", "生效"), 此刻()),
        )
        conn.commit()
        return {"桶键": 桶键, "状态": "生效"}
    finally:
        conn.close()


def _bf_touch_31(conn=None, 键: str = ""):
    from app.modules import 钉纪元对照账 as _m
    _ = _m.旧纪元确认放行(conn, 键)
    _ = _m.登记证明(conn)
    return _m.巡检包({ "touched": True })
