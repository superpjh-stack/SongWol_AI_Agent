import {useEffect,useState} from 'react';
import {ArrowUpRight} from 'lucide-react';
import {request,type DailyData,type Workspace} from '../types';
import {RecordList} from './Records';

export default function DailyLogistics({token,workspace,onAsk}:{token:string;workspace:Workspace;onAsk:(q:string,lot?:string)=>void}){
 const [day,setDay]=useState(workspace.meta.daily_anchor||'2026-10-09'),[kind,setKind]=useState<'inventory'|'plans'|'actuals'>('inventory');
 const [data,setData]=useState<DailyData|null>(null),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{const controller=new AbortController();setData(null);setError('');request<DailyData>(token,`/daily?start_date=${day}&end_date=${day}`,{signal:controller.signal}).then(setData).catch(e=>{if(!controller.signal.aborted)setError(e.message)});return()=>controller.abort()},[token,day,retry]);
 const totals=data?.daily_totals[0],future=day>(workspace.meta.daily_anchor||'2026-10-09');
 const labels={inventory:future?'예상 재고':'재고현황',plans:'출하계획',actuals:'출하실적'};
 return <section className="daily-logistics"><div className="operations-heading"><div><h2>일별 재고·출하</h2><p>{workspace.meta.daily_start}~{workspace.meta.daily_end} · 과거 15일 + 기준일 + 이후 15일</p></div><label className="field-label">조회 날짜<input aria-label="물류 조회 날짜" type="date" min={workspace.meta.daily_start} max={workspace.meta.daily_end} value={day} onChange={e=>{if(e.target.value)setDay(e.target.value)}}/></label></div>
  <div className="tabs">{Object.entries(labels).map(([key,label])=><button key={key} className={kind===key?'active':''} onClick={()=>setKind(key as typeof kind)}>{label}</button>)}</div>
  <p className="muted">{future?'미래 재고는 가상 예상치이며 출하실적은 아직 없습니다.':'09:00 기준 가상 스냅샷입니다. 실제 운영 기록이 아닙니다.'}</p>
  {error?<div className="error" role="alert">{error}<button onClick={()=>setRetry(v=>v+1)}>다시 조회</button></div>:!data?<p role="status" className="loading">일별 자료를 불러오는 중…</p>:<><div className="daily-summary"><strong>{labels[kind]} <span>{kind==='actuals'&&future?'실적 없음':Number(totals?.[kind==='inventory'?'inventory_quantity':kind==='plans'?'planned_quantity':'shipped_quantity']||0).toLocaleString()+' EA'}</span></strong><button className="quiet-button" onClick={()=>onAsk(`송월아, ${day} ${labels[kind]}을 알려줘`,'')}>이 날짜로 질문<ArrowUpRight size={15}/></button></div><RecordList rows={data[kind]}/></>}
 </section>;
}
