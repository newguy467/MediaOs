import { useState, useEffect } from "react";
function WidgetLayoutPage() {
  const [layout, setLayout] = useState([]);
  const [msg, setMsg] = useState('');
  const all = ['activity','queue','calendar','continue_watching','recent_scrobbles','games_wanted','tracking_summary','wanted','library','recent','health'];
  useEffect(()=>{
    fetch('/api/overhaul/widget-layout').then(r=>r.json()).then(d=>setLayout(d.layout||all)).catch(()=>setLayout(all));
  }, []);
  const toggle = (id) => {
    setLayout(prev => prev.includes(id) ? prev.filter(x=>x!==id) : [...prev, id]);
  };
  const save = async () => {
    const r = await fetch('/api/overhaul/widget-layout', { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ layout }) }).then(r=>r.json());
    setMsg(r.ok ? 'Saved' : JSON.stringify(r));
  };
  return (
    <div className="page-shell space-y-4">
      <h1 className="mr-page-title">Dashboard widgets</h1>
      <p className="text-sm opacity-60">Enable/disable widgets (Prismarr-style control). Order = list order.</p>
      {msg && <div className="alert alert-info text-xs py-2">{msg}</div>}
      <div className="flex flex-col gap-2 max-w-md">
        {all.map(id => (
          <label key={id} className="label cursor-pointer justify-start gap-3 bg-base-200 rounded-lg px-3 py-2">
            <input type="checkbox" className="checkbox checkbox-sm" checked={layout.includes(id)} onChange={()=>toggle(id)} />
            <span className="label-text text-sm">{id}</span>
          </label>
        ))}
      </div>
      <button type="button" className="btn btn-sm btn-primary" onClick={save}>Save layout</button>
    </div>
  );
}

export default WidgetLayoutPage;
