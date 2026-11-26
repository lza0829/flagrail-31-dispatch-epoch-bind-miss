import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

数据目录 = Path(
    os.environ.get("数据目录")
    or os.environ.get("DATA_DIR")
    or (Path(__file__).resolve().parent.parent / "data")
)
夹具目录 = Path(os.environ.get("夹具目录", Path(__file__).resolve().parent.parent.parent / "fixtures"))
_环境库路径 = (
    os.environ.get("数据库路径")
    or os.environ.get("DB_PATH")
    or os.environ.get("DATABASE_PATH")
    or os.environ.get("SQLITE_PATH")
)
if not _环境库路径:
    _数据库地址 = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI") or ""
    if _数据库地址.startswith("sqlite:///"):
        _环境库路径 = _数据库地址.removeprefix("sqlite:///")
库路径 = Path(_环境库路径) if _环境库路径 else (数据目录 / "灰度轨.db")
if _环境库路径:
    数据目录 = 库路径.parent



写锁 = threading.RLock()
_已确保结构: set[str] = set()

结构SQL = """
CREATE TABLE IF NOT EXISTS 站规 (
  键 TEXT PRIMARY KEY,
  值 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 开关版本 (
  版本键 TEXT PRIMARY KEY,
  开关键 TEXT NOT NULL,
  版本号 INTEGER NOT NULL,
  载荷 TEXT NOT NULL DEFAULT '{}',
  状态 TEXT NOT NULL DEFAULT '已入轨',
  入轨时 TEXT NOT NULL,
  说明 TEXT NOT NULL DEFAULT '',
  载荷纪元 INTEGER NOT NULL DEFAULT 1,
  载荷哈希 TEXT NOT NULL DEFAULT '',
  绑定策略 TEXT NOT NULL DEFAULT '纪元抬升'
);
CREATE TABLE IF NOT EXISTS 分桶规 (
  桶键 TEXT PRIMARY KEY,
  开关键 TEXT NOT NULL,
  桶类型 TEXT NOT NULL,
  规则 TEXT NOT NULL DEFAULT '{}',
  状态 TEXT NOT NULL DEFAULT '生效',
  更新时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 下发票 (
  票号 TEXT PRIMARY KEY,
  开关键 TEXT NOT NULL,
  版本键 TEXT NOT NULL,
  桶键 TEXT NOT NULL,
  状态 TEXT NOT NULL DEFAULT '待下发',
  下发时 TEXT NOT NULL DEFAULT '',
  世代 INTEGER NOT NULL DEFAULT 1,
  说明 TEXT NOT NULL DEFAULT '',
  载荷纪元 INTEGER NOT NULL DEFAULT 1,
  载荷哈希 TEXT NOT NULL DEFAULT '',
  钉纪元 INTEGER NOT NULL DEFAULT 1,
  钉哈希 TEXT NOT NULL DEFAULT '',
  下发钉纪元 INTEGER NOT NULL DEFAULT 1,
  下发钉哈希 TEXT NOT NULL DEFAULT '',
  钉住纪元 INTEGER NOT NULL DEFAULT 1,
  钉住哈希 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 回读证 (
  证号 TEXT PRIMARY KEY,
  票号 TEXT NOT NULL,
  边缘键 TEXT NOT NULL,
  所见版本键 TEXT NOT NULL DEFAULT '',
  结果 TEXT NOT NULL,
  回读时 TEXT NOT NULL,
  说明 TEXT NOT NULL DEFAULT '',
  所见纪元 INTEGER NOT NULL DEFAULT 0,
  所见哈希 TEXT NOT NULL DEFAULT '',
  所见载荷纪元 INTEGER NOT NULL DEFAULT 0,
  所见载荷哈希 TEXT NOT NULL DEFAULT '',
  回读所见纪元 INTEGER NOT NULL DEFAULT 0,
  回读所见哈希 TEXT NOT NULL DEFAULT '',
  载荷纪元 INTEGER NOT NULL DEFAULT 0,
  载荷哈希 TEXT NOT NULL DEFAULT '',
  有效 INTEGER NOT NULL DEFAULT 0,
  旧纪元 INTEGER NOT NULL DEFAULT 0,
  处置 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 命运账 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  对象类型 TEXT NOT NULL,
  对象键 TEXT NOT NULL,
  命运 TEXT NOT NULL,
  时刻 TEXT NOT NULL,
  说明 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 装载批次 (
  编号 TEXT PRIMARY KEY,
  时刻 TEXT NOT NULL,
  报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 轨贯验 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  时刻 TEXT NOT NULL,
  版本数 INTEGER NOT NULL,
  下发数 INTEGER NOT NULL,
  回读数 INTEGER NOT NULL,
  命运数 INTEGER NOT NULL,
  是否通过 INTEGER NOT NULL,
  说明 TEXT NOT NULL,
  核证报告 TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS 空桩 (
  名 TEXT PRIMARY KEY,
  状态 TEXT NOT NULL DEFAULT '空桩'
);
CREATE TABLE IF NOT EXISTS 载荷纪元史 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  版本键 TEXT NOT NULL,
  开关键 TEXT NOT NULL DEFAULT '',
  载荷纪元 INTEGER NOT NULL,
  载荷哈希 TEXT NOT NULL,
  载荷 TEXT NOT NULL DEFAULT '{}',
  动作 TEXT NOT NULL DEFAULT '入轨',
  时刻 TEXT NOT NULL,
  说明 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 作废旧钉 (
  编号 INTEGER PRIMARY KEY AUTOINCREMENT,
  票号 TEXT NOT NULL,
  开关键 TEXT NOT NULL DEFAULT '',
  版本键 TEXT NOT NULL,
  桶键 TEXT NOT NULL DEFAULT '',
  旧纪元 INTEGER NOT NULL DEFAULT 1,
  旧哈希 TEXT NOT NULL DEFAULT '',
  新纪元 INTEGER NOT NULL DEFAULT 1,
  新哈希 TEXT NOT NULL DEFAULT '',
  缘由 TEXT NOT NULL DEFAULT '载荷纪元抬升',
  时刻 TEXT NOT NULL,
  说明 TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_旧钉_版本 ON 作废旧钉(版本键);
CREATE INDEX IF NOT EXISTS idx_旧钉_票号 ON 作废旧钉(票号);
CREATE INDEX IF NOT EXISTS idx_纪元史_版本 ON 载荷纪元史(版本键, 载荷纪元);
"""

新增列 = {
    "开关版本": [
        ("载荷纪元", "INTEGER NOT NULL DEFAULT 1"),
        ("载荷哈希", "TEXT NOT NULL DEFAULT ''"),
        ("绑定策略", "TEXT NOT NULL DEFAULT '纪元抬升'"),
    ],
    "下发票": [
        ("载荷纪元", "INTEGER NOT NULL DEFAULT 1"),
        ("载荷哈希", "TEXT NOT NULL DEFAULT ''"),
        ("钉纪元", "INTEGER NOT NULL DEFAULT 1"),
        ("钉哈希", "TEXT NOT NULL DEFAULT ''"),
        ("下发钉纪元", "INTEGER NOT NULL DEFAULT 1"),
        ("下发钉哈希", "TEXT NOT NULL DEFAULT ''"),
        ("钉住纪元", "INTEGER NOT NULL DEFAULT 1"),
        ("钉住哈希", "TEXT NOT NULL DEFAULT ''"),
    ],
    "回读证": [
        ("所见纪元", "INTEGER NOT NULL DEFAULT 0"),
        ("所见哈希", "TEXT NOT NULL DEFAULT ''"),
        ("所见载荷纪元", "INTEGER NOT NULL DEFAULT 0"),
        ("所见载荷哈希", "TEXT NOT NULL DEFAULT ''"),
        ("回读所见纪元", "INTEGER NOT NULL DEFAULT 0"),
        ("回读所见哈希", "TEXT NOT NULL DEFAULT ''"),
        ("载荷纪元", "INTEGER NOT NULL DEFAULT 0"),
        ("载荷哈希", "TEXT NOT NULL DEFAULT ''"),
        ("有效", "INTEGER NOT NULL DEFAULT 0"),
        ("旧纪元", "INTEGER NOT NULL DEFAULT 0"),
        ("处置", "TEXT NOT NULL DEFAULT ''"),
    ],
    "轨贯验": [
        ("核证报告", "TEXT NOT NULL DEFAULT '{}'"),
    ],
}


def 确保结构(c: sqlite3.Connection) -> None:
    """幂等建表/补列，兼容已挂载旧 SQLite 卷的环境。"""

    c.executescript(结构SQL)
    for 表, 列们 in 新增列.items():
        已有 = {r[1] for r in c.execute(f"PRAGMA table_info({表})").fetchall()}
        for 列名, 列定义 in 列们:
            if 列名 not in 已有:
                c.execute(f"ALTER TABLE {表} ADD COLUMN {列名} {列定义}")
    c.commit()


def 连接() -> sqlite3.Connection:
    数据目录.mkdir(parents=True, exist_ok=True)
    路径键 = str(库路径)
    c = sqlite3.connect(库路径, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA busy_timeout = 30000")
    
    已有列 = {r[1] for r in c.execute("PRAGMA table_info(开关版本)").fetchall()}
    需要结构 = 路径键 == ":memory:" or "载荷纪元" not in 已有列
    if 需要结构:
        确保结构(c)
        if 路径键 != ":memory:":
            _已确保结构.add(路径键)
    return c


@contextmanager
def 写事务():
    """串行化关键写路径，并立即取得 SQLite 写锁。"""

    with 写锁:
        conn = 连接()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
