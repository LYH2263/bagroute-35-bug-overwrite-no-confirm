import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
type R = { id: number; name: string };
type Bag = { id: number; route_id: number; bag_index: number; weight_kg: number; volume_l: number; items: { stop_name: string }[] };
export default function PackPage() {
  const [routes, setRoutes] = useState<R[]>([]);
  const [rid, setRid] = useState<number | "">("");
  const [bags, setBags] = useState<Bag[]>([]);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const [needConfirm, setNeedConfirm] = useState(false);
  useEffect(() => { api<R[]>("/routes").then(r => { setRoutes(r); if (r[0]) setRid(r[0].id); }); }, []);
  useEffect(() => {
    if (rid === "") return;
    setMsg(""); setErr(""); setNeedConfirm(false);
    api<Bag[]>("/bags").then(all => setBags(all.filter(b => b.route_id === rid)));
  }, [rid]);
  async function run(confirmOverwrite: boolean) {
    setMsg(""); setErr("");
    try {
      const out = await api<Bag[]>("/pack", { method: "POST", body: JSON.stringify({ route_id: rid, confirm_overwrite: confirmOverwrite }) });
      setBags(out);
      setNeedConfirm(false);
      setMsg(`完成装袋：${out.length} 袋`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        // 未确认重装被服务端拒绝，旧袋明细/拒收/袋重未变，保持当前展示
        setNeedConfirm(true);
      }
      setErr(e instanceof Error ? e.message : String(e));
    }
  }
  return (<>
    <h2>装袋</h2>
    <div className="toolbar">
      <select value={rid} onChange={e => setRid(Number(e.target.value))}>{routes.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select>
      <button onClick={() => run(false)}>按路线顺序双约束装袋</button>
      {needConfirm && <button className="warn" onClick={() => run(true)}>确认覆盖重装</button>}
    </div>
    {needConfirm && <div className="err">该路线已有装袋结果，重新装袋将覆盖现有袋明细、拒收与袋重；确认请点「确认覆盖重装」。</div>}
    {msg && <div className="ok">{msg}</div>}
    {err && <div className="err">{err}</div>}
    {bags.map(b => (
      <div key={b.id}>
        <div className="mono">袋 {b.bag_index} · {b.weight_kg}kg / {b.volume_l}L</div>
        <div className="bag-row">{b.items.map((it, i) => <div className="bag-block" key={i}>{it.stop_name}</div>)}</div>
      </div>
    ))}
  </>);
}
