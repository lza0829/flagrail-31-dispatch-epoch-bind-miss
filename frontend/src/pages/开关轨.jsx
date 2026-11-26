import React, { useEffect, useMemo, useState } from "react";
import { get, post, postFixture } from "../api.js";

function short(h) {
  return h ? String(h).slice(0, 12) : "—";
}

export default function 开关轨() {
  const [rows, setRows] = useState([]);
  const [旧钉, set旧钉] = useState([]);
  const [讯, set讯] = useState("");
  const [误, set误] = useState("");
  const [cert, setCert] = useState(null);
  const [版本键, set版本键] = useState("");
  const [载荷文本, set载荷文本] = useState('{\n  "enabled": true,\n  "variant": "B"\n}');
  const [新纪元, set新纪元] = useState("");

  const 刷 = async () => {
    const [versions, pins] = await Promise.all([get("/开关版本"), get("/作废旧钉")]);
    setRows(versions);
    set旧钉(pins);
    if (!版本键 && versions[0]) set版本键(versions[0].版本键);
  };

  useEffect(() => { 刷().catch((e) => set误(String(e))); }, []);

  const 当前 = useMemo(() => rows.find((r) => r.版本键 === 版本键), [rows, 版本键]);

  const 选中版本 = (r) => {
    set版本键(r.版本键);
    try {
      set载荷文本(JSON.stringify(r.载荷, null, 2));
    } catch {
      set载荷文本(String(r.载荷 ?? "{}"));
    }
    set新纪元("");
    setCert(null);
  };

  const 提交改载荷 = async () => {
    set误(""); set讯("");
    let 载荷;
    try {
      载荷 = JSON.parse(载荷文本);
    } catch (e) {
      set误(`载荷 JSON 不合法：${e.message}`);
      return;
    }
    if (!当前) {
      set误("请先选择一个已入轨版本");
      return;
    }
    try {
      const body = {
        批次编号: `ui-载荷变更-${Date.now()}`,
        版本: [{
          开关键: 当前.开关键,
          版本号: 当前.版本号,
          版本键: 当前.版本键,
          载荷,
          说明: "开关轨页面改载荷再提交",
        }],
      };
      if (新纪元 !== "") body.版本[0].载荷纪元 = Number(新纪元);
      const out = await post("/入轨", body);
      const item = out.明细?.[0] || out.报告?.明细?.[0];
      set讯(item?.纪元变化
        ? `二次提交成功：纪元 ${item.旧纪元} → ${item.载荷纪元}，哈希 ${short(item.旧载荷哈希)} → ${short(item.载荷哈希)}`
        : "提交完成：载荷未变，幂等跳过，纪元不变");
      await 刷();
    } catch (e) {
      set误(String(e));
    }
  };

  const 核证 = async (key) => {
    set误("");
    try {
      setCert(await get(`/核证?版本键=${encodeURIComponent(key)}`));
    } catch (e) { set误(String(e)); }
  };

  return (
    <div>
      <h1 className="题">开关轨 · 载荷纪元</h1>
      <p className="述">
        同版本键、同版本号也可能被改载荷。当前纪元与 SHA-256 载荷哈希并列展示；改载荷再提交必须成功抬纪元，
        或按冻结口径显式拒绝。旧纪元钉票进入下方“作废旧钉”列表。
      </p>
      <div className="行">
        <button onClick={async () => { await postFixture("入轨样例"); await 刷(); set讯("已灌入轨样例"); }}>灌入轨样例</button>
        <button className="信" onClick={async () => {
          const r = await postFixture("载荷纪元样例");
          await 刷();
          set讯(`纪元夹具：二次成功=${r.报告.二次成功}，纪元变化=${r.报告.纪元变化}，旧核证=${r.报告.旧核证valid}，新核证=${r.报告.新核证valid}`);
        }}>灌载荷纪元夹具</button>
        <button className="次" onClick={() => 刷().catch((e) => set误(String(e)))}>刷新</button>
      </div>
      {讯 && <p className="讯 成">{讯}</p>}
      {误 && <p className="讯 败文">{误}</p>}

      {!rows.length ? <div className="空态">尚无版本，先灌入轨样例或载荷纪元样例</div> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>版本键</th><th>开关键</th><th>版本号</th>
                <th>当前纪元</th><th>载荷哈希</th><th>作废旧钉</th><th>状态</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.版本键} className={r.版本键 === 版本键 ? "选中行" : ""}>
                  <td><button className="linklike" onClick={() => 选中版本(r)}>{r.版本键}</button></td>
                  <td>{r.开关键}</td>
                  <td>{r.版本号}</td>
                  <td><span className="徽章 信 epoch">E{r.载荷纪元 ?? r.纪元}</span></td>
                  <td><code title={r.载荷哈希}>{short(r.载荷哈希)}</code></td>
                  <td>
                    {Array.isArray(r.作废旧钉) && r.作废旧钉.length ? (
                      <span className="徽章 警">{r.作废旧钉.length} 条旧钉</span>
                    ) : <span className="淡">无</span>}
                  </td>
                  <td><span className="徽章 通">{r.状态}</span></td>
                  <td><button className="次 mini" onClick={() => 核证(r.版本键)}>核证</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {当前 && (
        <section className="面板">
          <div className="面板头">
            <h2>改载荷再提交 · {当前.版本键}</h2>
            <span className="淡">当前 E{当前.载荷纪元} / <code>{short(当前.载荷哈希)}</code></span>
          </div>
          <label className="字段">
            <span>载荷 JSON（版本号保持 {当前.版本号} 不变）</span>
            <textarea value={载荷文本} onChange={(e) => set载荷文本(e.target.value)} rows={8} />
          </label>
          <div className="行">
            <label className="字段 inline">
              <span>新纪元（留空自动 +1）</span>
              <input value={新纪元} onChange={(e) => set新纪元(e.target.value)} placeholder={`应为 ${Number(当前.载荷纪元 || 1) + 1}`} />
            </label>
            <button className="信" onClick={提交改载荷}>改载荷并再提交</button>
          </div>
          <p className="述 mini-text">
            若显式采用“版本键载荷冻结”口径，可在请求体传 <code>绑定策略: "冻结"</code>；后端会以 409 明确拒绝二次修改。
          </p>
        </section>
      )}

      {cert && (
        <section className={"面板 核证 " + (cert.valid ? "ok" : "bad")}>
          <div className="面板头">
            <h2>核证路由 /api/核证</h2>
            <span className={"徽章 " + (cert.valid ? "通" : "败")}>{String(cert.valid)}</span>
          </div>
          <div className="kv">
            <span>纪元：<b>{cert.纪元 ?? cert.载荷纪元}</b></span>
            <span>载荷哈希：<code title={cert.载荷哈希}>{cert.载荷哈希}</code></span>
            {cert.原因 && <span className="败文">原因：{cert.原因}</span>}
          </div>
        </section>
      )}

      <section className="面板">
        <div className="面板头"><h2>作废旧钉列表</h2><span className="淡">纪元差必须在界面可见</span></div>
        {!旧钉.length ? <div className="空态">尚无作废旧钉</div> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>#</th><th>票号</th><th>版本键</th><th>旧纪元 → 新纪元</th><th>纪元差</th><th>旧哈希</th><th>新哈希</th><th>时刻</th><th>说明</th></tr></thead>
              <tbody>
                {旧钉.map((o) => (
                  <tr key={o.编号}>
                    <td>{o.编号}</td>
                    <td>{o.票号}</td>
                    <td>{o.版本键}</td>
                    <td><span className="纪元差"><b>E{o.旧纪元}</b> → <b className="通文">E{o.新纪元}</b></span></td>
                    <td><span className="徽章 警">+{o.新纪元 - o.旧纪元}</span></td>
                    <td><code title={o.旧哈希}>{short(o.旧哈希)}</code></td>
                    <td><code title={o.新哈希}>{short(o.新哈希)}</code></td>
                    <td>{o.时刻}</td>
                    <td className="note">{o.说明}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
