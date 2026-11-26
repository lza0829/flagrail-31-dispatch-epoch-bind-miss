import React, { useEffect, useState } from "react";
import { get, postFixture } from "../api.js";

export default function 命运账() {
  const [rows, setRows] = useState([]);
  const [讯, set讯] = useState("");
  const 刷 = async () => setRows(await get("/命运账"));
  useEffect(() => { 刷().catch((e) => set讯(String(e))); }, []);
  return (
    <div>
      <h1 className="题">命运账</h1>
      <p className="述">回滚 / 失效写命运。回滚票必须落命运条，否则贯验失败。</p>
      <div className="行">
        <button className="焰" onClick={async () => { await postFixture("回滚样例"); await 刷(); set讯("已灌回滚样例"); }}>灌回滚样例</button>
        <button className="次" onClick={() => 刷()}>刷新</button>
      </div>
      {讯 && <p className="讯">{讯}</p>}
      {!rows.length ? <div className="空态">尚无命运条</div> : (
        <table>
          <thead><tr><th>#</th><th>对象类型</th><th>对象键</th><th>命运</th><th>时刻</th><th>说明</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.编号}><td>{r.编号}</td><td>{r.对象类型}</td><td>{r.对象键}</td>
            <td><span className="徽章 败">{r.命运}</span></td><td>{r.时刻}</td><td>{r.说明}</td></tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
}
