import React, { useEffect, useState } from "react";
import { get, postFixture } from "../api.js";

export default function 分桶规() {
  const [rows, setRows] = useState([]);
  const [讯, set讯] = useState("");
  const 刷 = async () => setRows(await get("/分桶规"));
  useEffect(() => { 刷().catch((e) => set讯(String(e))); }, []);
  return (
    <div>
      <h1 className="题">分桶规</h1>
      <p className="述">百分比桶 / 名单桶 / 环境桶。下发前必须有生效分桶且开关键对齐。</p>
      <div className="行">
        <button onClick={async () => { await postFixture("分桶样例"); await 刷(); set讯("已灌分桶样例"); }}>灌分桶样例</button>
        <button className="次" onClick={() => 刷()}>刷新</button>
      </div>
      {讯 && <p className="讯">{讯}</p>}
      {!rows.length ? <div className="空态">尚无分桶</div> : (
        <table>
          <thead><tr><th>桶键</th><th>开关键</th><th>桶类型</th><th>规则</th><th>状态</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.桶键}><td>{r.桶键}</td><td>{r.开关键}</td><td>{r.桶类型}</td>
            <td><code>{typeof r.规则 === "string" ? r.规则 : JSON.stringify(r.规则)}</code></td>
            <td>{r.状态}</td></tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}
