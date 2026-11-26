import React, { useEffect, useMemo, useState } from "react";
import { get, post, postFixture } from "../api.js";

function short(h) { return h ? String(h).slice(0, 12) : "—"; }

export default function 回读台() {
  const [rows, setRows] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [讯, set讯] = useState("");
  const [误, set误] = useState("");
  const [form, setForm] = useState({
    票号: "", 边缘键: "edge-ui", 所见版本键: "",
    所见纪元: "", 所见哈希: "", 严格: false,
  });

  const 刷 = async () => {
    const [reads, ts] = await Promise.all([get("/回读证"), get("/下发票")]);
    setRows(reads);
    setTickets(ts);
    setForm((f) => f.票号 ? f : {
      ...f,
      票号: ts[0]?.票号 || "",
      所见版本键: ts[0]?.版本键 || "",
      所见纪元: ts[0]?.下发钉纪元 ?? ts[0]?.载荷纪元 ?? "",
      所见哈希: ts[0]?.下发钉哈希 || ts[0]?.载荷哈希 || "",
    });
  };
  useEffect(() => { 刷().catch((e) => set误(String(e))); }, []);

  const ticket = useMemo(() => tickets.find((t) => t.票号 === form.票号), [tickets, form.票号]);
  const 更新 = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const 选票 = (票号) => {
    const t = tickets.find((x) => x.票号 === 票号);
    setForm((f) => ({
      ...f,
      票号,
      所见版本键: t?.版本键 || "",
      所见纪元: t?.下发钉纪元 ?? t?.载荷纪元 ?? "",
      所见哈希: t?.下发钉哈希 || t?.载荷哈希 || "",
    }));
  };

  const 提交 = async () => {
    set误(""); set讯("");
    try {
      const body = {
        票号: form.票号,
        边缘键: form.边缘键,
        所见版本键: form.所见版本键,
        所见纪元: form.所见纪元 === "" ? undefined : Number(form.所见纪元),
        所见哈希: form.所见哈希,
        严格: form.严格,
      };
      const out = await post("/回读", body);
      set讯(`回读已记录：结果=${out.结果}，valid=${out.valid}，纪元差=${out.纪元差 ?? ""}`);
      await 刷();
    } catch (e) {
      set误(`已拒绝：${String(e).slice(0, 220)}`);
      await 刷();
    }
  };

  return (
    <div>
      <h1 className="题">回读台 · 所见哈希同票</h1>
      <p className="述">
        边缘回读不能只报版本键：同键载荷可能已抬纪元。所见纪元/哈希必须与下发票钉值同票；
        旧纪元确认会被旁置，或在严格策略下直接拒绝。界面保留纪元差与哈希证据。
      </p>
      <div className="行">
        <button onClick={async () => { await postFixture("回读样例"); await 刷(); set讯("已灌回读样例"); }}>灌回读样例</button>
        <button className="次" onClick={() => 刷().catch((e) => set误(String(e)))}>刷新</button>
      </div>
      {讯 && <p className="讯 成">{讯}</p>}
      {误 && <p className="讯 败文">{误}</p>}

      <section className="面板">
        <div className="面板头"><h2>记一条回读</h2><span className="淡">可故意把纪元/哈希改成旧值验证旁置或拒绝</span></div>
        <div className="form-grid">
          <label className="字段">
            <span>票号</span>
            <select value={form.票号} onChange={(e) => 选票(e.target.value)}>
              {tickets.map((t) => <option key={t.票号} value={t.票号}>{t.票号}（{t.状态} E{t.下发钉纪元}）</option>)}
            </select>
          </label>
          <label className="字段"><span>边缘键</span><input value={form.边缘键} onChange={(e) => 更新("边缘键", e.target.value)} /></label>
          <label className="字段"><span>所见版本键</span><input value={form.所见版本键} onChange={(e) => 更新("所见版本键", e.target.value)} /></label>
          <label className="字段"><span>所见纪元</span><input value={form.所见纪元} onChange={(e) => 更新("所见纪元", e.target.value)} /></label>
          <label className="字段 grow2"><span>所见哈希</span><input value={form.所见哈希} onChange={(e) => 更新("所见哈希", e.target.value)} /></label>
        </div>
        {ticket && (
          <div className="钉预览">
            <span>票面钉值：E{ticket.下发钉纪元} /</span>
            <code title={ticket.下发钉哈希 || ticket.载荷哈希}>{ticket.下发钉哈希 || ticket.载荷哈希}</code>
            {ticket.过期 && <span className="徽章 警">票面相对当前版本已过期</span>}
          </div>
        )}
        <div className="行">
          <button className="信" onClick={提交}>提交回读</button>
          <label className="checkline">
            <input type="checkbox" checked={form.严格} onChange={(e) => 更新("严格", e.target.checked)} />
            旧纪元按拒绝处理（默认旁置）
          </label>
        </div>
      </section>

      {!rows.length ? <div className="空态">尚无回读证</div> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>证号</th><th>票号</th><th>边缘</th><th>所见版本</th><th>所见纪元</th><th>所见哈希</th><th>纪元差</th><th>结果</th><th>valid</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.证号} className={r.结果 === "旁置" || r.结果 === "拒绝" ? "stale-row" : ""}>
                  <td>{r.证号}</td>
                  <td>{r.票号}</td>
                  <td>{r.边缘键}</td>
                  <td>{r.所见版本键}</td>
                  <td><span className="徽章 信">E{r.所见纪元 || "?"}</span></td>
                  <td><code title={r.所见哈希}>{short(r.所见哈希)}</code></td>
                  <td>{r.纪元差 ? <span className="徽章 警">+{r.纪元差}</span> : <span className="淡">0</span>}</td>
                  <td><span className={"徽章 " + (r.结果 === "确认" ? "通" : r.结果 === "旁置" ? "警" : "败")}>{r.结果}{r.旧纪元 ? " · 旧纪元" : ""}</span></td>
                  <td><span className={"徽章 " + (r.valid ? "通" : "败")}>{String(r.valid)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
