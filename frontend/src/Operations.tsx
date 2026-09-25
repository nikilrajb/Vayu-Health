import {authHeaders} from "./auth";
import { useEffect, useState } from "react";

type Ledger = {alerts: {id:string;city:string;peak_at:string;risk:number;quality:string;status:string;owner:string;note:string}[];checks:{city:string;at:string;ok:number;detail:string}[];counts:Record<string,number>;note:string;tasks:{id:string;city:string;zone:string;action:string;owner:string;due_at:string;status:string;evidence:string;verified_by:string}[];compliance:{due_assignments:number;verified_on_time:number;rate_pct:number|null;definition:string}};
const base = import.meta.env.VITE_API_URL || "";
export default function Operations({city}:{city:string}) {
  const [ledger,setLedger] = useState<Ledger|null>(null);
  const [owner,setOwner] = useState("");
  const [note,setNote] = useState("");
  const [error,setError] = useState("");
  const [busy,setBusy] = useState(false);
  const [zone,setZone]=useState("");
  const [action,setAction]=useState("");
  const [due,setDue]=useState("");
  async function taskRequest(path:string,body:unknown) {
    setBusy(true);setError("");
    try{const r=await fetch(`${base}/api/v1/${path}`,{method:"POST",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify(body)});if(!r.ok){const b=await r.json();throw Error(typeof b.detail==='string'?b.detail:'Check assignment details.');}await load();}
    catch(e){setError(String(e));}finally{setBusy(false);}
  }
  async function load() {
    try {const r=await fetch(`${base}/api/v1/operations`); if(!r.ok) throw Error("Unable to load local alert log"); setLedger(await r.json());}
    catch(e) {setError(String(e));}
  }
  useEffect(()=>{void load();},[]);
  async function update(id:string,status:string) {
    setBusy(true); setError("");
    try {const r=await fetch(`${base}/api/v1/operations/${encodeURIComponent(id)}`,{method:"POST",headers:{"Content-Type":"application/json",...authHeaders()},body:JSON.stringify({status,owner,note})});
      if(!r.ok) {const body=await r.json(); throw Error(typeof body.detail === "string" ? body.detail : "Enter your name and a note of at least five characters.");}
      await load(); setNote("");
    } catch(e) {setError(String(e));} finally {setBusy(false);}
  }
  return <article className="panel workflow">
    <span className="eyebrow">PERSISTENT OPERATOR LOG</span><h2>Alert acknowledgements</h2>
    <p>Run <code>run-monitor.cmd</code> to collect all locations. Alerts appear when forecast screening risk reaches 101. Review source quality and timing before taking action.</p>
    <button className="button" onClick={()=>void load()}>Refresh alert log</button>
    {error && <p role="alert">{error}</p>}
    <p>{ledger?.note}</p>
    <p>{ledger?.alerts.length || 0} recent alerts. Acknowledged: {ledger?.counts.acknowledged || 0}; resolved: {ledger?.counts.resolved || 0}.</p>
    {ledger?.checks.filter(c=>c.city===city).map(c=><p key={c.city}>{c.city}: {c.ok ? "Collection succeeded" : "Collection failed"} · {new Date(c.at).toLocaleString()}</p>)}
    <label>Assignee account username <input aria-label="Responsible operator" value={owner} onChange={e=>setOwner(e.target.value)} maxLength={100}/></label>
    <label>Action / evidence note <input aria-label="Action or evidence note" value={note} onChange={e=>setNote(e.target.value)} maxLength={2000}/></label>
    {ledger?.alerts.filter(a=>a.city===city).map(a=><div key={a.id} style={{borderTop:"1px solid",padding:"16px 0"}}>
      <h3>{a.city} · risk {a.risk} · {a.status}</h3><p>Peak {new Date(a.peak_at).toLocaleString()} · {a.quality}</p><p>{a.owner} {a.note}</p>
      {a.status!=="resolved" && <button className="button" disabled={busy || !owner.trim() || note.trim().length<5} onClick={()=>void update(a.id,a.status==="new" ? "acknowledged":"resolved")}>{a.status==="new" ? "Acknowledge":"Record resolution"}</button>}
    </div>)}
    <h2>Industrial assignments · {city}</h2>
    <p>Enter an existing operator account username above. Record a specific facility-approved action and deadline. Sign in as the assigned operator to acknowledge and complete it. A different account with reviewer role must verify the evidence; changing the assignee field does not change your signed-in identity.</p>
    <label>Facility or zone <input value={zone} onChange={e=>setZone(e.target.value)} /></label>
    <label>Assigned action <input value={action} onChange={e=>setAction(e.target.value)} /></label>
    <label>Completion deadline (your local time) <input type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/></label>
    <button className="button" disabled={busy||!owner.trim()||zone.trim().length<2||action.trim().length<5||!due} onClick={()=>void taskRequest('assignments',{city,zone,action,owner,due_at:new Date(due).toISOString()})}>Create assignment</button>
    <p>All-location on-time verified workflow completion: {ledger?.compliance?.rate_pct==null?'Not yet measurable':`${ledger.compliance.rate_pct}%`} ({ledger?.compliance?.verified_on_time||0}/{ledger?.compliance?.due_assignments||0} due assignments).</p>
    <p>{ledger?.compliance?.definition}</p>
    {ledger?.tasks?.filter(t=>t.city===city).map(t=><div key={t.id} style={{borderTop:'1px solid',padding:'12px 0'}}><h3>{t.zone} · {t.status}</h3><p>{t.action} · Owner: {t.owner} · Due: {new Date(t.due_at).toLocaleString()}</p><p>Evidence: {t.evidence||'Not submitted'} {t.verified_by&&`· Reviewer: ${t.verified_by}`}</p>{t.status!=='verified'&&<button className="button" disabled={busy||!owner.trim()||note.trim().length<5} onClick={()=>void taskRequest(`assignments/${t.id}`,{status:t.status==='assigned'?'acknowledged':t.status==='acknowledged'?'completed':'verified',actor:owner,evidence:note})}>{t.status==='assigned'?'Acknowledge assignment':t.status==='acknowledged'?'Submit completion evidence':'Verify evidence'}</button>}</div>)}
  </article>;
}
