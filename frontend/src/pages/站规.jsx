import React, { useEffect, useState } from "react";
import { get } from "../api.js";

export default function 站规() {
  const [规, set规] = useState({});
  useEffect(() => { get("/站规").then(set规); }, []);
  return (
    <div>
      <h1 className="题">站规</h1>
      <p className="述">仓级口径只读。禁名单话术不进 Prompt，写在规划/题单。</p>
      <table>
        <thead><tr><th>键</th><th>值</th></tr></thead>
        <tbody>{Object.entries(规).map(([k, v]) => (
          <tr key={k}><td>{k}</td><td>{v}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}
