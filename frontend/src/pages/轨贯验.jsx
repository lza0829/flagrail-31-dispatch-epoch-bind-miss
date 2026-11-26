import React, { useEffect, useState } from "react";
import { get, post } from "../api.js";

export default function 轨贯验() {
  const [rows, setRows] = useState([]);
  const [讯, set讯] = useState("");
  const 刷 = async () => setRows(await get("/贯验"));
  useEffect(() => { 刷().catch((e) => set讯(String(e))); }, []);
  return (
    <div>
      <h1 className="题">轨贯验</h1>
      <p className="述">入轨版本 ↔ 下发票 ↔ 回读 ↔ 命运 互证。悬空下发 / 回读拧花 / 回滚无命运 → 不通过。</p>
      <div className="行">
        <button onClick={async () => {
          try {
            const g = await post("/贯验");
            await 刷();
            set讯(g.是否通过
              ? `通过 · 纪元/哈希核证 ${g.核证项?.length || 0} 项 · 作废旧钉 ${g.旧钉数 ?? 0} · 旁置 ${g.旁置数 ?? 0}`
              : g.说明);
          } catch (e) { set讯(String(e)); }
        }}>跑贯验</button>
        <button className="次" onClick={() => 刷()}>刷新</button>
      </div>
      {讯 && <p className="讯">{讯}</p>}
      {!rows.length ? <div className="空态">尚未跑过贯验</div> : (
        <table>
          <thead><tr><th>#</th><th>时刻</th><th>版本</th><th>下发</th><th>回读</th><th>命运</th><th>结果</th><th>说明</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.编号}><td>{r.编号}</td><td>{r.时刻}</td><td>{r.版本数}</td><td>{r.下发数}</td>
            <td>{r.回读数}</td><td>{r.命运数}</td>
            <td><span className={"徽章 " + (r.是否通过 ? "通" : "败")}>{r.是否通过 ? "通过" : "失败"}</span></td>
            <td>{r.说明}</td></tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}
