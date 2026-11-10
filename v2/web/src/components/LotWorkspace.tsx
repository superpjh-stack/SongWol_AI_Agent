import {useEffect,useState} from 'react';
import {ArrowUpRight,Search} from 'lucide-react';
import {request,type Workspace,type LotTrace} from '../types';
import {RecordList} from './Records';

const sections:[keyof LotTrace,string][]=[['work_order','작업지시·생산'],['order','수주'],['quality','품질검사'],['conditions','공정 측정'],['inventory','원단·완제품 재고'],['shipment','출하 · 주문 기준 연결'],['claims','클레임 · LOT 또는 주문 연결']];
export default function LotWorkspace({token,workspace,lot,onSelect,onAsk}:{token:string;workspace:Workspace;lot:string;onSelect:(lot:string)=>void;onAsk:(question:string,lot:string)=>void}){
 const [search,setSearch]=useState(''),[trace,setTrace]=useState<LotTrace|null>(null),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{
  setTrace(null);setError('');if(!lot)return;
  const controller=new AbortController();request<LotTrace>(token,'/lots/'+encodeURIComponent(lot),{signal:controller.signal}).then(setTrace).catch(e=>{if(!controller.signal.aborted)setError(e.message)});
  return()=>controller.abort();
 },[token,lot,retry]);
 const lots=workspace.lots.filter(l=>`${l.print_lot} ${l.order_no} ${l.status}`.toLowerCase().includes(search.toLowerCase()));
 const job=trace?.work_order[0];
 return <section className="lot-workspace"><div className="page-heading"><span className="eyebrow">LOT TRACEABILITY</span><h1>한 장의 타월, 연결된 기록</h1><p>원단부터 인쇄·검사·출하까지 LOT를 따라 확인하세요.</p></div>
  <div className="lot-grid"><section className="lot-browser"><label className="search"><Search size={16}/><input aria-label="LOT 검색" placeholder="LOT, 주문번호, 상태 검색" value={search} onChange={e=>setSearch(e.target.value)}/></label><p className="section-label">인쇄 LOT <span>{lots.length}개</span></p><div className="lot-list">{lots.map(l=><button className={lot===l.print_lot?'selected':''} key={l.print_lot} onClick={()=>onSelect(l.print_lot)}><strong>{l.print_lot}</strong><span>{l.order_no}<em className="status">{l.status}</em></span></button>)}</div>{!lots.length&&<p className="empty-note">일치하는 LOT가 없습니다.</p>}</section>
  <section className="lot-detail" aria-live="polite">{!lot?<div className="empty-detail"><span className="eyebrow">SELECT A LOT</span><h2>확인할 LOT를 선택하세요.</h2><p>생산 수량, 품질검사와 연결된 원본 기록을 보여드립니다.</p></div>:error?<div className="error" role="alert">{error}<button onClick={()=>setRetry(v=>v+1)}>다시 조회</button></div>:!trace?<p className="loading" role="status">LOT 기록을 불러오는 중…</p>:<><div className="detail-heading"><div><span className="eyebrow">PRINT LOT</span><h2>{lot}</h2><p>{String(job?.process||'공정 미확인')} · {String(job?.status||'상태 미확인')}</p></div><button className="primary" onClick={()=>onAsk(`송월아, ${lot}의 품질과 출하 상태를 알려줘`,lot)}>이 LOT로 질문<ArrowUpRight size={16}/></button></div><div className="lot-metrics">{[['planned_qty','계획'],['good_qty','양품'],['defect_qty','불량']].map(([key,label])=><div key={key}><span>{label}</span><strong>{typeof job?.[key]==='number'?job[key].toLocaleString('ko-KR'):'미확인'}<small> EA</small></strong></div>)}</div><p className="muted">{workspace.meta.as_of} 기준 샘플 · 출하는 주문 기준 연결이며 해당 LOT의 출하 수량을 확정하지 않습니다.</p>{sections.map(([key,title])=><section className="trace-section" key={key}><h3>{title}<span>{trace[key].length}건</span></h3><RecordList rows={trace[key]}/></section>)}</>}</section></div>
 </section>;
}
