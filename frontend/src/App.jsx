import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import 轨台 from "./pages/轨台.jsx";
import 开关轨 from "./pages/开关轨.jsx";
import 分桶规 from "./pages/分桶规.jsx";
import 下发票 from "./pages/下发票.jsx";
import 回读台 from "./pages/回读台.jsx";
import 命运账 from "./pages/命运账.jsx";
import 轨贯验 from "./pages/轨贯验.jsx";
import 站规 from "./pages/站规.jsx";
import 核证钉纪元对照 from "./pages/钉纪元对照.jsx";

const 主链 = [
  ["/", "轨台"],
  ["/开关轨", "开关轨"],
  ["/分桶规", "分桶规"],
  ["/下发票", "下发票"],
  ["/回读台", "回读台"],
  ["/命运账", "命运账"],
  ["/轨贯验", "轨贯验"],
];
const 次链 = [["/站规", "站规"],
  ["/钉纪元对照", "钉纪元对照核证"]];

export default function App() {
  return (
    <div className="壳">
      <aside className="侧轨">
        <div className="侧标">
          <div className="侧英">Flagrail</div>
          <div className="侧名">灰度轨</div>
          <div className="侧骨">入轨 → 分桶下发 → 回读 → 回滚互证</div>
        </div>
        <nav className="侧导">
          {主链.map(([to, l]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "亮" : "")}>
              {l}
            </NavLink>
          ))}
          {次链.map(([to, l]) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "亮 次链" : "次链")}>
              {l}
            </NavLink>
          ))}
        </nav>
        <div className="侧脚">INFRA · MIDDLEWARE · :6800</div>
      </aside>
      <div className="主壳">
        <main className="主">
          <Routes>
            <Route path="/" element={<轨台 />} />
            <Route path="/开关轨" element={<开关轨 />} />
            <Route path="/分桶规" element={<分桶规 />} />
            <Route path="/下发票" element={<下发票 />} />
            <Route path="/回读台" element={<回读台 />} />
            <Route path="/命运账" element={<命运账 />} />
            <Route path="/轨贯验" element={<轨贯验 />} />
            <Route path="/站规" element={<站规 />} />
            <Route path="/钉纪元对照" element={<核证钉纪元对照 />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
