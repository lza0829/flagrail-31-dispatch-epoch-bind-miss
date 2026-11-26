import React, { useEffect, useMemo, useState } from "react";
import { get, post, postFixture } from "../api.js";

function short(h) { return h ? String(h).slice(0, 12) : "—"; }

export default function 下发票() {
  const [rows, setRows] = useState([]);
  const [versions, setVersions] = useState([]);
  const [buckets, setBuckets] = useState([]);
  const [讯, set讯] = useState("");
  const [误, set误] = useState("");
  const [form, setForm] = useState({ 版本键: "", 桶键: "", 票号: "", 说明: "页面钉票" });

  const 刷 = async () => {
    const [tickets, vs, bs] = await Promise.all([
      get("/下发票"), get("/开关版本"), get("/分桶规"),
    ]);
    setRows(tickets); setVersions(vs); setBuckets(bs);
    setForm((f) => {
      const 版本键 = f.版本键 || vs[0]?.版本键 || "";
      const v = vs.find((x) => x.版本键 === 版本键);
      const b = bs.find((x) => x.开关键 === v?.开关键)?.桶键 || f.桶键;
      return { ...f, 版本键, 桶键: f.桶键 || b || "" };
    });
  };

  useEffect(() => { 刷().catch((e) => set误(String(e))); }, []);

  const selected = useMemo(
    () => versions.find((v) => v.版本键 === form.版本键),
    [versions, form.版本键],
  );
  const selectedBucket = useMemo(
    () => buckets.find((b) => b.桶键 === form.桶键),
    [buckets, form.桶键],
  );

  const 更新 = (k, val) => setForm((f) => ({ ...f, [k]: val }));

  const 下发 = async () => {
    set误(""); set讯("");
    if (!selected) { set误("请选择版本"); return; }
    if (!selectedBucket) { set误("请选择生效分桶"); return; }
    try {
      const out = await post("/下发", {
        ...form,
        载荷纪元: selected.载荷纪元,
        纪元: selected.载荷纪元,
        载荷哈希: selected.载荷哈希,
        期望纪元: selected.载荷纪元,
        期望哈希: selected.载荷哈希,
      });
      set讯(out.幂等 ? `票号 ${out.票号} 已幂等下发，钉 E${out.载荷纪元}/${short(out.载荷哈希)}`
        : `已下发 ${out.票号}，钉住 E${out.载荷纪元}/${short(out.载荷哈希)}`);
      await 刷();
    } catch (e) { set误(String(e)); }
  };

  const 重钉 = async (r) => {
    set误(""); set讯("");
    try {
      const out = await post("/下发", {
        票号: r.票号, 版本键: r.版本键, 桶键: r.桶键,
        载荷纪元: r.当前载荷纪元, 载荷哈希: r.当前载荷哈希,
        说明: "新纪元重钉",
      });
      set讯(`已重钉 ${r.票号} → E${out.载荷纪元}/${short(out.载荷哈希)}`);
      await 刷();
    } catch (e) { set误(String(e)); }
  };

  const 试旧哈希 = async (r) => {
    set误(""); set讯("");
    try {
      await post("/下发", {
        票号: r.票号 + "-stale-check", 版本键: r.版本键, 桶键: r.桶键,
        载荷纪元: r.载荷纪元, 载荷哈希: r.载荷哈希,
      });
      set误("旧哈希竟被接受，违反禁止静默钉旧哈希");
    } catch (e) {
      set误(`后端已拒绝旧钉：${String(e).slice(0, 180)}`);
    }
  };

  return (
    <div>
      <h1 className="题">下发票 · 钉纪元 / 钉哈希</h1>
      <p className="述">
        每张票必须与“版本键 + 载荷纪元 + 载荷哈希”同票。页面下发时显式展示并提交当前钉值；
        <strong>禁止静默钉旧哈希</strong>：纪元抬升后仍显示旧哈希的票会标红，只能作废或按新纪元重钉，不能静默当新票。
      </p>
      <div className="行">
        <button onClick={async () => { await postFixture("下发样例"); await 刷(); set讯("已灌下发样例"); }}>灌下发样例</button>
        <button className="次" onClick={() => 刷().catch((e) => set误(String(e)))}>刷新</button>
      </div>
      {讯 && <p className="讯 成">{讯}</p>}
      {误 && <p className="讯 败文">{误}</p>}

      <section className="面板">
        <div className="面板头"><h2>新建/重发票</h2><span className="淡">钉票预览不是旧哈希</span></div>
        <div className="form-grid">
          <label className="字段">
            <span>版本键</span>
            <select value={form.版本键} onChange={(e) => {
              const v = versions.find((x) => x.版本键 === e.target.value);
              const b = buckets.find((x) => x.开关键 === v?.开关键);
              setForm((f) => ({ ...f, 版本键: e.target.value, 桶键: b?.桶键 || f.桶键 }));
            }}>
              {versions.map((v) => <option key={v.版本键} value={v.版本键}>{v.版本键} · E{v.载荷纪元}</option>)}
            </select>
          </label>
          <label className="字段">
            <span>桶键</span>
            <select value={form.桶键} onChange={(e) => 更新("桶键", e.target.value)}>
              {buckets.map((b) => <option key={b.桶键} value={b.桶键}>{b.桶键}</option>)}
            </select>
          </label>
          <label className="字段">
            <span>票号（留空自动生成）</span>
            <input value={form.票号} onChange={(e) => 更新("票号", e.target.value)} placeholder="票-版本键-桶键" />
          </label>
        </div>
        {selected && (
          <div className="钉预览">
            <span>将钉住：</span>
            <b>E{selected.载荷纪元}</b>
            <code title={selected.载荷哈希}>{selected.载荷哈希}</code>
            <span className="徽章 信">当前纪元/哈希</span>
          </div>
        )}
        <div className="行"><button className="信" onClick={下发}>按下发并钉住当前纪元哈希</button></div>
      </section>

      {!rows.length ? <div className="空态">尚无下发票（需先入轨+分桶）</div> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>票号</th><th>版本键</th><th>桶键</th><th>状态</th><th>钉纪元</th><th>钉载荷哈希</th><th>当前纪元/哈希</th><th>纪元差</th><th>操作</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.票号} className={r.过期 ? "stale-row" : ""}>
                  <td>{r.票号}</td>
                  <td>{r.版本键}</td>
                  <td>{r.桶键}</td>
                  <td><span className={"徽章 " + (r.状态 === "已下发" ? "通" : r.状态 === "已作废" ? "警" : "败")}>{r.状态}</span></td>
                  <td><span className="徽章 信">E{r.下发钉纪元 ?? r.载荷纪元}</span></td>
                  <td><code title={r.下发钉哈希 || r.载荷哈希}>{short(r.下发钉哈希 || r.载荷哈希)}</code></td>
                  <td>
                    <div>E{r.当前载荷纪元} / <code title={r.当前载荷哈希}>{short(r.当前载荷哈希)}</code></div>
                    {r.过期 && <div className="败文">旧钉，禁止静默当新</div>}
                  </td>
                  <td>{r.纪元差 ? <span className="徽章 警">+{r.纪元差}</span> : <span className="淡">0</span>}</td>
                  <td className="actions">
                    {r.过期 && <button className="mini 信" onClick={() => 重钉(r)}>新纪元重钉</button>}
                    {r.过期 && <button className="mini 次" onClick={() => 试旧哈希(r)}>试旧哈希</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
