from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.db import 连接
from app.modules.载荷纪元 import 计算载荷哈希
from app.services import 入轨, 分桶, 下发, 回读, 贯验
from app.services.载荷纪元 import 版本哈希, 版本纪元, 核证


def 确保短语夹具基座() -> None:
    """让“旧纪元回读/新纪元重下发”两个静态夹具可在空库上单独运行。"""

    版本键 = "epoch.demo@1"
    开关键 = "epoch.demo"
    桶键 = "epoch.demo-gray10"
    票号 = "票-epoch-demo-1-gray10"
    旧载荷 = {"limit": 10, "mode": "old"}
    新载荷 = {"limit": 20, "mode": "new"}
    旧哈希 = 计算载荷哈希(旧载荷)
    新哈希 = 计算载荷哈希(新载荷)

    conn = 连接()
    try:
        v = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (版本键,)).fetchone()
        t = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (票号,)).fetchone()
        need_create = v is None
        old_state = bool(
            v is not None
            and 版本纪元(v) == 1
            and 版本哈希(v) == 旧哈希
        )
        new_state = bool(v is not None and 版本哈希(v) == 新哈希)
    finally:
        conn.close()

    if need_create:
        入轨.入一批({"版本": [{
            "开关键": 开关键, "版本号": 1, "版本键": 版本键,
            "载荷": 旧载荷, "载荷纪元": 1, "说明": "短语夹具基座 v1",
        }]})

    分桶.写桶({
        "桶键": 桶键, "开关键": 开关键, "桶类型": "百分比",
        "规则": {"percent": 10, "salt": "epoch-demo"}, "状态": "生效",
    })

    conn = 连接()
    try:
        t = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (票号,)).fetchone()
        v = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (版本键,)).fetchone()
        old_state = bool(v is not None and 版本哈希(v) == 旧哈希)
    finally:
        conn.close()

    if t is None and old_state:
        下发.下一票({"票号": 票号, "版本键": 版本键, "桶键": 桶键})

    conn = 连接()
    try:
        v = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (版本键,)).fetchone()
        current_hash = 版本哈希(v) if v else ""
    finally:
        conn.close()

    if current_hash != 新哈希:
        入轨.入一批({"版本": [{
            "开关键": 开关键, "版本号": 1, "版本键": 版本键,
            "载荷": 新载荷, "说明": "短语夹具基座：载荷变更，纪元抬升",
        }]})


def 跑载荷纪元场景(体: dict | None = None) -> dict:
    """端到端夹具：改载荷再提交 → 旧纪元回读旁置 → 新纪元重下发 → 新哈希确认。"""

    体 = 体 or {}
    版本键 = 体.get("版本键") or "epoch.demo@1"
    开关键 = 体.get("开关键") or "epoch.demo"
    桶键 = 体.get("桶键") or "epoch.demo-gray10"
    票号 = 体.get("票号") or "票-epoch-demo-1-gray10"
    旧载荷 = 体.get("旧载荷") or {"limit": 10, "mode": "old"}
    新载荷 = 体.get("新载荷") or {"limit": 20, "mode": "new"}

    第一次 = 入轨.入一批({
        "批次编号": f"{体.get('批次编号', '载荷纪元场景')}-入轨v1",
        "版本": [{
            "开关键": 开关键, "版本号": 1, "版本键": 版本键,
            "载荷": 旧载荷, "载荷纪元": 1, "说明": "载荷纪元夹具 v1",
        }],
    })
    第一次项 = 第一次["明细"][0]

    分桶.写桶({
        "桶键": 桶键, "开关键": 开关键, "桶类型": "百分比",
        "规则": {"percent": 10, "salt": "epoch-demo"}, "状态": "生效",
    })

    旧下发 = 下发.下一票({
        "票号": 票号, "版本键": 版本键, "桶键": 桶键, "说明": "旧纪元钉票",
    })

    旧确认 = 回读.记回读({
        "证号": f"证-{票号}-edge-ok",
        "票号": 票号, "边缘键": "edge-ok",
        "所见版本键": 版本键, "说明": "旧纪元当时确认",
    })

    第二次 = 入轨.入一批({
        "批次编号": f"{体.get('批次编号', '载荷纪元场景')}-改载荷",
        "版本": [{
            "开关键": 开关键, "版本号": 1, "版本键": 版本键,
            "载荷": 新载荷, "说明": "版本号不变，修改载荷，纪元自动 +1",
        }],
    })
    第二次项 = 第二次["明细"][0]
    旧纪元 = 第二次项["旧纪元"]
    新纪元 = 第二次项["载荷纪元"]
    旧哈希 = 第二次项["旧载荷哈希"]
    新哈希 = 第二次项["载荷哈希"]

    旧纪元回读 = 回读.记回读({
        "证号": f"证-{票号}-edge-stale",
        "票号": 票号, "边缘键": "edge-stale",
        "所见版本键": 版本键,
        "所见纪元": 旧纪元,
        "所见哈希": 旧哈希,
        "说明": "边缘仍报旧哈希，必须旁置/拒绝确认",
    })

    新纪元下发 = 下发.下一票({
        "票号": 票号, "版本键": 版本键, "桶键": 桶键,
        "载荷纪元": 新纪元, "载荷哈希": 新哈希,
        "说明": "新纪元重钉/重下发",
    })

    新确认 = 回读.记回读({
        "证号": f"证-{票号}-edge-new",
        "票号": 票号, "边缘键": "edge-new",
        "所见版本键": 版本键,
        "所见纪元": 新纪元,
        "所见哈希": 新哈希,
        "说明": "新纪元哈希确认",
    })

    旧核证 = 核证({
        "票号": 票号, "所见纪元": 旧纪元, "所见哈希": 旧哈希,
    })
    新核证 = 核证({
        "票号": 票号, "所见纪元": 新纪元, "所见哈希": 新哈希,
    })
    贯验结果 = 贯验.跑贯验()

    return {
        "类型": "载荷纪元场景",
        "批次编号": 体.get("批次编号") or "载荷纪元样例",
        "第一次": 第一次项,
        "第二次": 第二次项,
        "二次成功": bool(第二次项.get("成功")),
        "纪元是否变化": bool(第二次项.get("纪元变化")),
        "旧纪元": 旧纪元,
        "新纪元": 新纪元,
        "旧哈希": 旧哈希,
        "新哈希": 新哈希,
        "旧下发": 旧下发,
        "旧确认": 旧确认,
        "旧纪元回读": 旧纪元回读,
        "新纪元下发": 新纪元下发,
        "新确认": 新确认,
        "旧核证": 旧核证,
        "新核证": 新核证,
        "贯验": 贯验结果,
        "报告": {
            "二次成功": bool(第二次项.get("成功")),
            "纪元变化": bool(第二次项.get("纪元变化")),
            "旧纪元回读结果": 旧纪元回读["结果"],
            "新回读结果": 新确认["结果"],
            "旧核证valid": bool(旧核证["valid"]),
            "新核证valid": bool(新核证["valid"]),
            "贯验通过": bool(贯验结果["是否通过"]),
        },
    }


def 跑并发核证(次数: int = 12) -> dict:
    """并发更新载荷与下发，检查最终生效票没有“新纪元标签 + 旧哈希”。"""

    违规 = []
    结果 = []

    def 一轮(i: int) -> dict:
        开关键 = f"concurrent.epoch.{i}"
        版本键 = f"{开关键}@1"
        桶键 = f"{开关键}-bucket"
        票号 = f"ticket-{开关键}"
        入轨.入一批({"版本": [{
            "开关键": 开关键, "版本号": 1, "版本键": 版本键,
            "载荷": {"v": 1, "i": i},
        }]})
        分桶.写桶({"桶键": 桶键, "开关键": 开关键, "规则": {"percent": 100}})
        gate = Barrier(2)

        def 更新():
            gate.wait()
            return 入轨.入一批({"版本": [{
                "开关键": 开关键, "版本号": 1, "版本键": 版本键,
                "载荷": {"v": 2, "i": i},
            }]})

        def 发票():
            gate.wait()
            try:
                return 下发.下一票({"票号": 票号, "版本键": 版本键, "桶键": 桶键})
            except Exception as e:  
                return {"错误": str(e)}

        with ThreadPoolExecutor(max_workers=2) as pool:
            uf = pool.submit(更新)
            tf = pool.submit(发票)
            up = uf.result()
            ticket_resp = tf.result()

        conn = 连接()
        try:
            v = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (版本键,)).fetchone()
            t = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (票号,)).fetchone()
            cur_epoch = v["载荷纪元"]
            cur_hash = v["载荷哈希"]
            pin_epoch = t["下发钉纪元"]
            pin_hash = t["下发钉哈希"]
            bad_label = pin_epoch == cur_epoch and pin_hash != cur_hash
            effective_old = t["状态"] == "已下发" and (pin_epoch != cur_epoch or pin_hash != cur_hash)
            if bad_label or effective_old:
                违规.append({
                    "版本键": 版本键, "票号": 票号, "状态": t["状态"],
                    "当前纪元": cur_epoch, "当前哈希": cur_hash,
                    "钉纪元": pin_epoch, "钉哈希": pin_hash,
                    "badLabel": bad_label, "effectiveOld": effective_old,
                })
            item = {
                "i": i, "票号": 票号, "状态": t["状态"],
                "当前纪元": cur_epoch, "钉纪元": pin_epoch,
                "当前哈希": cur_hash, "钉哈希": pin_hash,
                "更新成功": up.get("成功", False),
                "发票响应": ticket_resp,
            }
            结果.append(item)
            return item
        finally:
            conn.close()

    for i in range(max(1, 次数)):
        一轮(i)

    return {
        "valid": not 违规,
        "次数": 次数,
        "违规数": len(违规),
        "违规": 违规,
        "结果": 结果,
    }
