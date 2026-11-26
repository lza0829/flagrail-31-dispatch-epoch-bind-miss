import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import 夹具目录, 连接
from app.services import 入轨, 分桶, 下发, 回读, 命运, 贯验, 目录, 载荷纪元 as 纪元服务
from app.services import 场景

路由 = APIRouter(prefix="/api")


class 入轨请求(BaseModel):
    批次编号: str = ""
    版本: list = Field(default_factory=list)


class 分桶请求(BaseModel):
    桶键: str
    开关键: str
    桶类型: str = "百分比"
    规则: dict = Field(default_factory=dict)
    状态: str = "生效"


class 下发请求(BaseModel):
    票号: str = ""
    版本键: str
    桶键: str
    说明: str = ""


class 回读请求(BaseModel):
    证号: str = ""
    票号: str
    边缘键: str
    所见版本键: str = ""
    结果: str = "确认"
    说明: str = ""


class 回滚请求(BaseModel):
    票号: str
    说明: str = ""


class 失效请求(BaseModel):
    版本键: str
    说明: str = ""


@路由.get("/健康")
def 健康():
    return {
        "正常": True,
        "项目": "灰度轨",
        "领域": "基础设施",
        "子方向": "中间件",
        "骨架": "开关版本入轨→分桶灰度下发→回读确认→失效/回滚互证",
        "载荷纪元": "已实装",
    }


@路由.get("/总览")
def 取总览():
    return 目录.总览()


@路由.get("/站规")
def 站规():
    conn = 连接()
    try:
        return {r["键"]: r["值"] for r in conn.execute("SELECT 键, 值 FROM 站规")}
    finally:
        conn.close()


@路由.get("/开关版本")
@路由.get("/versions")
@路由.get("/switch-versions")
def 列版本(状态: str = ""):
    conn = 连接()
    try:
        if 状态:
            rows = conn.execute(
                "SELECT * FROM 开关版本 WHERE 状态=? ORDER BY 入轨时 DESC", (状态,)
            )
        else:
            rows = conn.execute("SELECT * FROM 开关版本 ORDER BY 入轨时 DESC")
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["载荷"] = json.loads(d["载荷"])
            except Exception:
                pass
            epoch = 纪元服务.版本纪元(r)
            h = 纪元服务.版本哈希(r)
            d.update({
                "纪元": epoch,
                "当前纪元": epoch,
                "当前载荷纪元": epoch,
                "载荷纪元": epoch,
                "载荷哈希": h,
                "当前哈希": h,
                "当前载荷哈希": h,
                "valid": bool(h),
                "哈希有效": bool(h),
            })
            d["作废旧钉"] = 纪元服务.列作废旧钉(d["版本键"])
            out.append(d)
        return out
    finally:
        conn.close()


@路由.get("/开关轨")
def 开关轨别名(状态: str = ""):
    return 列版本(状态)


@路由.get("/载荷纪元")
@路由.get("/payload-epoch")
@路由.get("/payload-epochs")
def 载荷纪元总览():
    版本 = 列版本()
    旧钉 = 纪元服务.列作废旧钉()
    核 = 纪元服务.全量核证()
    return {
        "策略": {
            "改载荷": "纪元抬升",
            "备选口径": "版本键载荷冻结时二次提交返回 409",
            "旧纪元回读": "旁置；请求显式严格/拒绝时返回 409",
        },
        "valid": 核["valid"],
        "版本": 版本,
        "items": 版本,
        "作废旧钉": 旧钉,
        "旧钉": 旧钉,
        "核证": 核,
    }


@路由.post("/载荷纪元")
@路由.post("/payload-epoch")
@路由.post("/payload-epochs")
def 载荷纪元提交(体: dict):
    return 入轨.入一批(体)


@路由.post("/载荷纪元/更新")
def 载荷纪元更新(体: dict):
    return 入轨.入一批(体)


@路由.post("/更新载荷")
def 更新载荷别名(体: dict):
    return 入轨.入一批(体)


@路由.get("/分桶规")
def 列分桶():
    conn = 连接()
    try:
        out = []
        for r in conn.execute("SELECT * FROM 分桶规 ORDER BY 更新时 DESC"):
            d = dict(r)
            try:
                d["规则"] = json.loads(d["规则"])
            except Exception:
                pass
            out.append(d)
        return out
    finally:
        conn.close()


def _票字典(conn, r) -> dict:
    d = dict(r)
    v = conn.execute("SELECT * FROM 开关版本 WHERE 版本键=?", (r["版本键"],)).fetchone()
    pin_epoch = 纪元服务.票钉纪元(r)
    pin_hash = 纪元服务.票钉哈希(r)
    cur_epoch = 纪元服务.版本纪元(v) if v else pin_epoch
    cur_hash = 纪元服务.版本哈希(v) if v else pin_hash
    current = pin_epoch == cur_epoch and (not cur_hash or pin_hash == cur_hash)
    d.update({
        "纪元": pin_epoch,
        "epoch": pin_epoch,
        "载荷纪元": pin_epoch,
        "payloadEpoch": pin_epoch,
        "钉纪元": pin_epoch,
        "pinnedEpoch": pin_epoch,
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
        "纪元差": max(0, cur_epoch - pin_epoch),
        "epochDelta": max(0, cur_epoch - pin_epoch),
        "钉住当前": current,
        "pinnedToCurrent": current,
        "过期": not current,
        "stale": not current,
        "valid": bool(current and r["状态"] in ("已下发", "灰度中")),
        "ticketNo": r["票号"],
        "versionKey": r["版本键"],
        "bucketKey": r["桶键"],
        "status": r["状态"],
    })
    return d


@路由.get("/下发票")
@路由.get("/tickets")
def 列下发(状态: str = ""):
    conn = 连接()
    try:
        if 状态:
            rows = conn.execute(
                "SELECT * FROM 下发票 WHERE 状态=? ORDER BY 下发时 DESC", (状态,)
            )
        else:
            rows = conn.execute("SELECT * FROM 下发票 ORDER BY 下发时 DESC")
        return [_票字典(conn, r) for r in rows]
    finally:
        conn.close()


@路由.get("/作废旧钉")
@路由.get("/旧钉")
@路由.get("/stale-pins")
@路由.get("/void-pins")
def 取作废旧钉(版本键: str = ""):
    return 纪元服务.列作废旧钉(版本键)


@路由.get("/旧钉/列表")
def 旧钉别名2(版本键: str = ""):
    return 纪元服务.列作废旧钉(版本键)


@路由.get("/回读证")
@路由.get("/readbacks")
def 列回读():
    conn = 连接()
    try:
        rows = []
        for r in conn.execute("SELECT * FROM 回读证 ORDER BY 回读时 DESC LIMIT 200"):
            d = dict(r)
            t = conn.execute("SELECT * FROM 下发票 WHERE 票号=?", (r["票号"],)).fetchone()
            pin_epoch = 纪元服务.票钉纪元(t) if t else int(r["钉纪元"] if "钉纪元" in r.keys() else 0) or 0
            pin_hash = 纪元服务.票钉哈希(t) if t else ""
            seen_epoch = int(r["所见纪元"] or r["所见载荷纪元"] or 0)
            seen_hash = r["所见哈希"] or r["所见载荷哈希"] or r["回读所见哈希"] or ""
            valid = r["结果"] == "确认" and (not pin_hash or not seen_hash or seen_hash == pin_hash)
            d.update({
                "status": "stale-epoch-quarantined" if d.get("结果") == "旁置" and (d.get("旧纪元") or r["旧纪元"]) else d.get("结果"),
                "状态": "旧纪元旁置" if d.get("结果") == "旁置" and (d.get("旧纪元") or r["旧纪元"]) else d.get("结果"),
                "category": "staleEpoch" if (bool(r["旧纪元"]) or r["结果"] in ("旁置", "拒绝")) else "",
                "类别": "旧纪元" if (bool(r["旧纪元"]) or r["结果"] in ("旁置", "拒绝")) else "",
                "seenEpoch": seen_epoch,
                "所见纪元": seen_epoch,
                "所见载荷纪元": seen_epoch,
                "回读所见纪元": seen_epoch,
                "epoch": seen_epoch or pin_epoch,
                "纪元": seen_epoch or pin_epoch,
                "seenHash": seen_hash,
                "所见哈希": seen_hash,
                "所见载荷哈希": seen_hash,
                "回读所见哈希": seen_hash,
                "payloadHash": seen_hash,
                "载荷哈希": seen_hash,
                "pinnedEpoch": pin_epoch,
                "钉纪元": pin_epoch,
                "下发钉纪元": pin_epoch,
                "pinnedHash": pin_hash,
                "钉哈希": pin_hash,
                "下发钉哈希": pin_hash,
                "valid": bool(valid),
                "epochDelta": max(0, pin_epoch - seen_epoch) if seen_epoch else 0,
                "纪元差": max(0, pin_epoch - seen_epoch) if seen_epoch else 0,
                "stale": bool(r["旧纪元"]) or r["结果"] in ("旁置", "拒绝"),
                "旧纪元": bool(r["旧纪元"]) or r["结果"] in ("旁置", "拒绝"),
                "ticketNo": r["票号"],
                "edgeKey": r["边缘键"],
                "result": r["结果"],
            })
            rows.append(d)
        return rows
    finally:
        conn.close()


@路由.get("/命运账")
def 列命运():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 命运账 ORDER BY 编号 DESC LIMIT 100")]
    finally:
        conn.close()


@路由.get("/批次")
def 列批次():
    conn = 连接()
    try:
        out = []
        for r in conn.execute("SELECT * FROM 装载批次 ORDER BY 时刻 DESC LIMIT 30"):
            d = dict(r)
            try:
                d["报告"] = json.loads(d["报告"])
            except Exception:
                pass
            out.append(d)
        return out
    finally:
        conn.close()


@路由.get("/空桩")
def 列空桩():
    conn = 连接()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM 空桩 ORDER BY 名")]
    finally:
        conn.close()


@路由.post("/入轨")
def 做入轨(体: dict):
    return 入轨.入一批(体)


@路由.post("/开关版本")
@路由.post("/开关轨")
@路由.post("/versions")
@路由.post("/switch-versions")
def 开关版本写入别名(体: dict):
    return 入轨.入一批(体)


@路由.post("/分桶")
def 做分桶(体: 分桶请求):
    return 分桶.写桶(体.model_dump())


@路由.post("/下发")
@路由.post("/dispatch")
@路由.post("/tickets")
def 做下发(体: dict):
    return 下发.下一票(体)


@路由.post("/回读")
@路由.post("/readback")
@路由.post("/readbacks")
def 做回读(体: dict):
    return 回读.记回读(体)


@路由.post("/回滚")
def 做回滚(体: 回滚请求):
    return 命运.回滚票(体.model_dump())


@路由.post("/失效")
def 做失效(体: 失效请求):
    return 命运.失效版本(体.model_dump())


@路由.get("/核证")
@路由.get("/certify")
@路由.get("/attest")
async def 核证查询(request: Request):
    return 纪元服务.核证(dict(request.query_params))


@路由.post("/核证")
@路由.post("/certify")
@路由.post("/attest")
def 核证提交(体: dict):
    return 纪元服务.核证(体)


@路由.get("/核证/{version_key}")
async def 核证路径(version_key: str, request: Request):
    q = dict(request.query_params)
    q["版本键"] = version_key
    q["versionKey"] = version_key
    return 纪元服务.核证(q)


@路由.get("/载荷纪元/核证")
async def 纪元核证查询(request: Request):
    return 纪元服务.核证(dict(request.query_params))


@路由.post("/载荷纪元/核证")
def 纪元核证提交(体: dict):
    return 纪元服务.核证(体)


@路由.get("/纪元核证")
async def 短核证查询(request: Request):
    return 纪元服务.核证(dict(request.query_params))


@路由.post("/纪元核证")
def 短核证提交(体: dict):
    return 纪元服务.核证(体)


@路由.get("/verify")
async def verify_get(request: Request):
    return 纪元服务.核证(dict(request.query_params))


@路由.post("/verify")
def verify_post(体: dict):
    return 纪元服务.核证(体)


@路由.get("/载荷核证")
async def 载荷核证查询(request: Request):
    return 纪元服务.核证(dict(request.query_params))


@路由.post("/载荷核证")
def 载荷核证提交(体: dict):
    return 纪元服务.核证(体)


@路由.get("/核证载荷纪元")
async def 核证载荷纪元查询(request: Request):
    return 纪元服务.核证(dict(request.query_params))


@路由.post("/核证载荷纪元")
def 核证载荷纪元提交(体: dict):
    return 纪元服务.核证(体)


@路由.get("/载荷纪元核证")
async def 载荷纪元核证别名查询(request: Request):
    return 纪元服务.核证(dict(request.query_params))


@路由.post("/载荷纪元核证")
def 载荷纪元核证别名提交(体: dict):
    return 纪元服务.核证(体)


@路由.get("/payload-epoch/verify")
async def payload_epoch_verify_get(request: Request):
    return 纪元服务.核证(dict(request.query_params))


@路由.post("/payload-epoch/verify")
def payload_epoch_verify_post(体: dict):
    return 纪元服务.核证(体)


@路由.post("/载荷纪元/并发核证")
def 载荷纪元并发核证(体: dict | None = None):
    次数 = int((体 or {}).get("次数", 12))
    return 场景.跑并发核证(次数)


_夹具名映射 = {
    "payload-epoch-sample": "载荷纪元样例",
    "payload_epoch_sample": "载荷纪元样例",
    "change-payload-resubmit": "改载荷再提交",
    "resubmit-payload": "改载荷再提交",
    "stale-epoch-readback": "旧纪元回读",
    "old-epoch-readback": "旧纪元回读",
    "new-epoch-redispatch": "新纪元重下发",
    "redispatch-new-epoch": "新纪元重下发",
    "payload-update-dispatch-concurrency": "更新与下发并发",
    "update-dispatch-concurrency": "更新与下发并发",
}


def _执行命名夹具(请求名: str, 请求体: dict | None = None):
    请求体 = 请求体 or {}
    名 = (
        请求名
        or 请求体.get("名")
        or 请求体.get("夹具名")
        or 请求体.get("名称")
        or 请求体.get("name")
        or 请求体.get("fixture")
        or 请求体.get("fixtureName")
        or "入轨样例"
    )
    名 = _夹具名映射.get(str(名), str(名))

    
    if 名 in ("旧纪元回读", "新纪元重下发"):
        场景.确保短语夹具基座()

    路径 = 夹具目录 / f"{名}.json"
    if not 路径.exists():
        raise HTTPException(404, f"夹具不存在:{名}")
    体 = json.loads(路径.read_text(encoding="utf-8"))
    类型 = 体.get("类型", "入轨")
    if 类型 == "载荷纪元场景":
        return 场景.跑载荷纪元场景(体)
    if 类型 == "载荷纪元并发":
        次数 = int(请求体.get("次数") or 体.get("次数", 20))
        return 场景.跑并发核证(次数)
    if 类型 == "入轨":
        return 入轨.入一批(体)
    if 类型 == "分桶":
        outs = [分桶.写桶(x) for x in 体.get("分桶") or []]
        return {"类型": "分桶", "结果": outs}
    if 类型 == "下发":
        return 下发.装下发夹具(体)
    if 类型 == "回读":
        return 回读.装回读夹具(体)
    if 类型 == "回滚":
        return 命运.回滚票(体)
    raise HTTPException(400, f"未知夹具类型:{类型}")


@路由.post("/装载/夹具")
@路由.post("/装载夹具")
@路由.post("/fixtures/load")
async def 装夹具(
    request: Request,
    名: str = "",
    夹具名: str = "",
    name: str = "",
    fixture: str = "",
    fixtureName: str = "",
):
    请求体 = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            请求体 = await request.json()
        except Exception:
            请求体 = {}
    return _执行命名夹具(名 or 夹具名 or name or fixtureName or fixture, 请求体)


@路由.post("/夹具/{fixture_name}")
@路由.post("/fixtures/{fixture_name}/load")
def 装路径夹具(fixture_name: str):
    return _执行命名夹具(fixture_name)


@路由.post("/贯验")
def 做贯验():
    return 贯验.跑贯验()


@路由.get("/贯验")
def 列贯验():
    conn = 连接()
    try:
        out = []
        for r in conn.execute("SELECT * FROM 轨贯验 ORDER BY 编号 DESC LIMIT 20"):
            d = dict(r)
            try:
                d["核证报告"] = json.loads(d.get("核证报告") or "{}")
                d["核证"] = d["核证报告"]
            except Exception:
                pass
            out.append(d)
        return out
    finally:
        conn.close()

from app.modules import 钉纪元对照账 as _bf_mod_31


@路由.get("/核证/钉纪元对照")
def 取核证_31(键: str | None = None):
    conn = 连接()
    try:
        return _bf_mod_31.查现场(conn, 键)
    finally:
        conn.close()


@路由.post("/核证/钉纪元对照/巡检")
def 巡检核证_31(payload: dict | None = None):
    return _bf_mod_31.巡检包(payload or {})

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

