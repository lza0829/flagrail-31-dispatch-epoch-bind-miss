from app.db import 连接, 结构SQL
from app.modules.载荷纪元 import 计算载荷哈希

建表 = 结构SQL


def 此刻() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 初始化库() -> None:
    conn = 连接()
    try:
        conn.executescript(结构SQL)
        if conn.execute("SELECT COUNT(*) AS c FROM 站规").fetchone()["c"] == 0:
            for k, v in {
                "站名": "灰度轨",
                "领域": "基础设施",
                "子方向": "中间件",
                "默认灰度比": "10",
                "回读齐套策略": "全边缘确认才可晋升",
                "骨架": "开关版本入轨→分桶灰度下发→回读确认→失效/回滚互证",
                "载荷绑定策略": "纪元抬升",
                "旧纪元回读策略": "旁置",
            }.items():
                conn.execute("INSERT INTO 站规(键, 值) VALUES (?, ?)", (k, v))
        else:
            conn.execute(
                "INSERT OR IGNORE INTO 站规(键, 值) VALUES ('载荷绑定策略', '纪元抬升')"
            )
            conn.execute(
                "INSERT OR IGNORE INTO 站规(键, 值) VALUES ('旧纪元回读策略', '旁置')"
            )

        
        for r in conn.execute("SELECT 版本键, 载荷, 载荷哈希 FROM 开关版本"):
            if not r["载荷哈希"]:
                h = 计算载荷哈希(r["载荷"])
                conn.execute(
                    "UPDATE 开关版本 SET 载荷哈希=? WHERE 版本键=?",
                    (h, r["版本键"]),
                )

        
        for t in conn.execute("SELECT * FROM 下发票"):
            v = conn.execute(
                "SELECT 载荷纪元, 载荷哈希 FROM 开关版本 WHERE 版本键=?",
                (t["版本键"],),
            ).fetchone()
            epoch = int(v["载荷纪元"]) if v and v["载荷纪元"] else 1
            h = v["载荷哈希"] if v else ""
            if not t["钉哈希"] and h:
                conn.execute(
                    """UPDATE 下发票 SET
                         载荷纪元=?, 载荷哈希=?, 钉纪元=?, 钉哈希=?,
                         下发钉纪元=?, 下发钉哈希=?, 钉住纪元=?, 钉住哈希=?
                       WHERE 票号=?""",
                    (epoch, h, epoch, h, epoch, h, epoch, h, t["票号"]),
                )

        
        for rd in conn.execute("SELECT * FROM 回读证 WHERE 所见哈希='' OR 所见哈希 IS NULL"):
            t = conn.execute(
                "SELECT * FROM 下发票 WHERE 票号=?", (rd["票号"],)
            ).fetchone()
            if not t:
                continue
            epoch = t["下发钉纪元"] or t["钉纪元"] or t["载荷纪元"] or 1
            h = t["下发钉哈希"] or t["钉哈希"] or t["载荷哈希"] or ""
            if h:
                conn.execute(
                    """UPDATE 回读证 SET
                         所见纪元=?, 所见哈希=?, 所见载荷纪元=?, 所见载荷哈希=?,
                         回读所见纪元=?, 回读所见哈希=?, 载荷纪元=?, 载荷哈希=?
                       WHERE 证号=?""",
                    (epoch, h, epoch, h, epoch, h, epoch, h, rd["证号"]),
                )

        
        for name in [
            "分桶比例冲突", "名单百分比互斥", "回读截止收口", "下发回读计划同票",
            "开关键竞态准入", "偏差隔离升", "环境域绑定", "失效回声处置",
            "意图去重键", "回滚槽互斥", "变体必填准入", "回读时间窗",
            "比例热切命运", "边缘名册门槛", "金丝雀影子道", "载荷纪元",
            "回声冲突裁定", "失效写闸", "跨环境串扰", "轨贯验三联",
            
            "名单与百分比互斥", "回读超时旁置", "半截下发回滚", "双版本同键并发",
            "回读偏差拒升全量", "环境桶隔离", "失效后幽灵回读", "下发票幂等键",
            "回滚窗互斥", "变体载荷契约", "边缘时钟漂移", "分桶重切",
            "全量晋升闸", "影子轨对照", "配置世代戳", "回读仲裁策略",
        ]:
            状态 = "已实装" if name == "载荷纪元" else "空桩"
            conn.execute(
                "INSERT INTO 空桩(名, 状态) VALUES (?, ?) "
                "ON CONFLICT(名) DO UPDATE SET 状态=excluded.状态",
                (name, 状态),
            )
        conn.commit()
    finally:
        conn.close()

EXTRA_DDL = '''
CREATE TABLE IF NOT EXISTS 钉纪元对照账表 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  对照号 TEXT, 票号 TEXT, 钉死纪元 TEXT, 新票号 TEXT, 状态 TEXT,
  时刻 TEXT NOT NULL DEFAULT '',
  载荷 TEXT NOT NULL DEFAULT '{}'
);
'''
