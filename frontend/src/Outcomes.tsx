import {authHeaders} from "./auth";
import {useEffect,useState} from 'react';
type Task={id:string;city:string;zone:string;action:string;status:string};
type Report={hours_per_window:number;observed_reduction_pct:number|null;control_adjusted_change_percentage_points:number;note:string};
const base=import.meta.env.VITE_API_URL||'';
export default function Outcomes({city}:{city:string}) {
  const [tasks,setTasks]=useState<Task[]>([]),[task,setTask]=useState(''),[csv,setCsv]=useState(''),[error,setError]=useState('');
  const [reports,setReports]=useState<{task_id:string;at:string;report:Report}[]>([]),[busy,setBusy]=useState(false);
  const [preview,setPreview]=useState<Report|null>(null);
  async function previewCsv(){setError('');try{const r=await fetch(`${base}/api/v1/outcomes/preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({csv_text:csv})});const d=await r.json();if(!r.ok)throw Error(d.detail);setPreview(d);}catch(e){setError(String(e));}}
  async function load(){try{const r=await fetch(`${base}/api/v1/operations`);if(!r.ok)throw Error('Cannot load outcome records');const d=await r.json();setTasks(d.tasks||[]);setReports(d.outcomes||[]);}catch(e){setError(String(e));}}
  useEffect(()=>{void load();setTask('');},[city]);
  async function submit(){setBusy(true);setError('');try{const r=await fetch(`${base}/api/v1/outcomes`,{method:'POST',headers:{'Content-Type':'application/json',...authHeaders()},body:JSON.stringify({task_id:task,csv_text:csv})});if(!r.ok){const b=await r.json();throw Error(typeof b.detail==='string'?b.detail:'Check the CSV format and size.');}await load();}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <article className="panel workflow"><span className="eyebrow">MEASURED OUTCOME REVIEW</span><h2>Compare measured high-risk hours</h2><p>Upload actual paired intervention/reference measurements for continuous, equal-length before/after windows, at least 24 hours each. This is separate from the scenario planner.</p><p>CSV columns: period, site, timestamp, pm25_ugm3, pm10_ugm3. Period: before/after. Site: intervention/reference. Use timezone-aware timestamps on hourly boundaries.</p>
    <div className="workflow-tools"><a href={`${base}/api/v1/samples/measurement-template.csv`} download>Blank measurement template</a><a href={`${base}/api/v1/samples/outcome-synthetic.csv`} download>Synthetic example (preview only)</a><a href={`${base}/api/v1/samples/FIELD_PROTOCOL.md`} download>Field protocol</a></div><button className="button" onClick={()=>void load()}>Refresh completed assignments</button>
    <label>Completed assignment <select value={task} onChange={e=>setTask(e.target.value)}><option value="">Select an assignment</option>{tasks.filter(t=>t.city===city&&['completed','verified'].includes(t.status)).map(t=><option key={t.id} value={t.id}>{t.zone}: {t.action}</option>)}</select></label>
    <label>Measured CSV <input type="file" accept=".csv,text/csv" onChange={async e=>{const f=e.target.files?.[0];setCsv('');setPreview(null);if(f&&f.size<=200000)setCsv(await f.text());else if(f)setError('CSV must be under 200 KB.');}}/></label>
    <button className="button" disabled={!csv} onClick={()=>void previewCsv()}>Preview calculation without saving</button>{preview&&<p>Preview only: reduction {preview.observed_reduction_pct ?? "undefined"}%; reference-adjusted change {preview.control_adjusted_change_percentage_points} percentage points. {preview.note}</p>}<button className="button primary" disabled={busy||!task||!csv} onClick={()=>void submit()}>Evaluate and save evidence</button>{error&&<p role="alert">{error}</p>}
    {reports.filter(r=>tasks.some(t=>t.id===r.task_id&&t.city===city)).map((r,i)=><div key={i}><h3>Recorded {new Date(r.at).toLocaleString()}</h3><p>{r.report.hours_per_window} measured hours per window. Unadjusted reduction: {r.report.observed_reduction_pct==null?'Undefined: baseline had no high-risk hours':`${r.report.observed_reduction_pct}%`}. Reference-adjusted change: {r.report.control_adjusted_change_percentage_points} percentage points.</p><p>{r.report.note}</p></div>)}
  </article>;
}
