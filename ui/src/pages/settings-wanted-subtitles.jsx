import { useState, useEffect } from "react";
function WantedSubtitlesPage({ setPage }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState('');
  useEffect(()=>{
    fetch('/api/tools/wanted-subtitles').then(r=>r.json()).then(d=>setItems(Array.isArray(d)?d:(d.items||[]))).catch(()=>setItems([])).finally(()=>setLoading(false));
  }, []);
  async function fetchSubs(row) {
    setMsg('Searching…');
    try {
      const path = row.kind==='movie' ? `/api/movies/${row.id}/subtitles` : `/api/tv/episodes/${row.id}/subtitles`;
      const r = await fetch(path, {method:'POST'}).then(x=>x.json()).catch(()=>({}));
      setMsg(JSON.stringify(r).slice(0,120));
    } catch(e){ setMsg(String(e.message||e)); }
  }
  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex justify-between items-center">
        <div><h1 className="mr-page-title">Wanted Subtitles</h1>
        <p className="text-sm opacity-50">Bazarr-style wanted list — OpenSubtitles (+ configured providers). Settings → Subtitles for API keys.</p></div>
        <button type="button" className="btn btn-sm" onClick={()=>setPage&&setPage('settings-subtitles')}>Subtitle settings</button>
      </div>
      {loading ? (
        <div className="space-y-2">
          <div className="skeleton h-10 w-full" />
          <div className="skeleton h-10 w-full" />
          <div className="skeleton h-10 w-full" />
          <div className="skeleton h-10 w-3/4" />
        </div>
      ) : (
        <table className="table table-sm"><thead><tr><th>Type</th><th>Title</th><th>Path</th><th></th></tr></thead><tbody>
          {items.map((row,i)=>(
            <tr key={i}><td className="text-xs">{row.kind}</td><td className="text-sm font-medium">{row.title}</td>
            <td className="text-xs font-mono opacity-50 truncate max-w-xs">{row.file_path||'—'}</td>
            <td><button type="button" className="btn btn-xs btn-primary" onClick={()=>fetchSubs(row)}>Fetch</button></td></tr>
          ))}
          {!items.length && <tr><td colSpan={4} className="opacity-40">Nothing listed</td></tr>}
        </tbody></table>
      )}
      {msg && <p className="text-xs opacity-60">{msg}</p>}
    </div>
  );
}



export default WantedSubtitlesPage;
export { WantedSubtitlesPage };
