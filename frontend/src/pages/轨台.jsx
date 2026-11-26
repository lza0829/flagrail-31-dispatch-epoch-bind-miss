import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { get, post, postFixture } from "../api.js";

export default function 轨台() {
  const [概, set概] = useState(null);
  const [讯, set讯] = useState("");
  const 刷 = async () => set概(await get("/总览"));
  useEffect(() => {
    刷().catch((e) => set讯(String(e)));
  }, []);

  const 跑通 = async () => {
    set讯("RUNNING…");
    try {
      await postFixture("入轨样例");
      await postFixture("分桶样例");
      await postFixture("下发样例");
      await postFixture("回读样例");
      const g = await post("/贯验");
      await 刷();
      set讯(g.是否通过 ? "OK · 主链贯通" : `FAIL · ${g.说明}`);
    } catch (e) {
      set讯(String(e));
    }
  };

  return (
    <section className="英雄">
      <div className="英雄英">feature flag rail</div>
      <h1 className="英雄名">灰度轨</h1>
      <p className="英雄骨">
        开关版本入轨，按分桶灰度下发，边缘回读确认后才能谈晋升或回滚——中间件控制面，不是配置 CRUD。
      </p>
      <div className="行">
        <button className="信" onClick={跑通}>
          跑通主链
        </button>
        <button className="次" onClick={() => 刷().catch((e) => set讯(String(e)))}>
          刷新刻度
        </button>
        <Link to="/开关轨" style={{ alignSelf: "center", color: "var(--信)", fontWeight: 600, marginLeft: 4 }}>
          从开关轨开始 →
        </Link>
      </div>
      {讯 && <p className="讯">{讯}</p>}
      {概 && (
        <div className="轨刻">
          <span>
            <i>01</i>
            <b>{概.开关版本}</b>版本
          </span>
          <span>
            <i>02</i>
            <b>{概.分桶规}</b>分桶
          </span>
          <span>
            <i>03</i>
            <b>{概.已下发}</b>已下发
          </span>
          <span>
            <i>04</i>
            <b>{概.确认回读}</b>回读确认
          </span>
          <span>
            <i>05</i>
            <b>{概.命运条}</b>命运
          </span>
        </div>
      )}
    </section>
  );
}
