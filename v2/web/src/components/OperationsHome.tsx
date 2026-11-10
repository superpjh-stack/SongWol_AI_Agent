import {useEffect,useState} from 'react';
import {ArrowUpRight,ArrowRight} from 'lucide-react';
import DailyLogistics from './DailyLogistics';
import {request,summaryLabels,type Row,type Workspace} from '../types';

const categories=[{key:'open_orders',table:'orders',name:'진행 주문',question:'진행 주문과 납기를 알려줘'}, {key:'quality_holds',table:'lot_quality',name:'품질 보류',question:'품질 보류 LOT를 보여줘'}, {key:'stock_issues',table:'inventory',name:'재고 주의',question:'안전재고 미달 품목을 알려줘'}, {key:'shipment_pending',table:'shipments',name:'출하 승인 대기',question:'미승인 출하 목록을 보여줘'}];
function included(key:string,r:Row){return key==='open_orders'?r.status!=='완료':key==='quality_holds'?r.result==='보류':key==='stock_issues'?r.stock_status==='안전재고 미달':r.approval==='미승인'}
export default function OperationsHome({token,workspace,onLot,onAsk}:{token:string;workspace:Workspace;onLot:(lot:string)=>void;onAsk:(q:string,lot?:string)=>void}){
 const [category,setCategory]=useState(categories[0]),[rows,setRows]=useState<Row[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 useEffect(()=>{const controller=new AbortController();setRows([]);setLoading(true);setError('');request<Row[]>(token,'/tables/'+category.table,{signal:controller.signal}).then(setRows).catch(e=>{if(!controller.signal.aborted)setError(e.message)}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});return()=>controller.abort()},[token,category,retry]);
 const filtered=rows.filter(r=>included(category.key,r));
 return <section className="operations-home"><div className="page-heading"><span className="eyebrow">OPERATIONS OVERVIEW</span><h1>현장의 기록을 한눈에.</h1><p>먼저 확인할 주문과 품질, 재고·출하 상태입니다.</p></div><div className="overview-kpis">{categories.map(c=><button key={c.key} className={c.key===category.key?'selected':''} onClick={()=>setCategory(c)}><span>{summaryLabels[c.key]}<ArrowUpRight size={16}/></span><strong>{workspace.summary[c.key]}<small>건</small></strong><span className="kpi-caption">관련 기록 확인</span></button>)}</div>
 <div className="operations-heading"><div><h2>{category.name}</h2><p>원본 첫 10개에서 조건에 맞는 기록을 표시합니다. 위 집계는 전체 DB 기준입니다.</p></div><button className="quiet-button" onClick={()=>onAsk('송월아, '+category.question,'')}>이 현황 질문하기<ArrowUpRight size={16}/></button></div>
 {loading?<p className="loading" role="status">현장 기록을 불러오는 중…</p>:error?<div className="error" role="alert">{error}<button onClick={()=>setRetry(v=>v+1)}>다시 조회</button></div>:<div className="table-scroll"><table><thead><tr><th>기록 / 품목</th><th>주문 / LOT</th><th>확인 내용</th><th>상태</th><th>연결</th></tr></thead><tbody>{filtered.map((r,i)=>{
  const linkedLot=typeof r.print_lot==='string'?r.print_lot:workspace.lots.find(l=>l.order_no===r.order_no||l.print_lot===r.fabric_lot||l.fabric_lot===r.fabric_lot)?.print_lot;
  return <tr key={i}><td><strong>{String(r.order_no&&category.key==='open_orders'?r.order_no:r.inspection_id||r.shipment_no||r.item_code)}</strong><small>{String(r.customer||r.item_name||'')}</small></td><td className="mono">{String(r.print_lot||r.fabric_lot||r.order_no||'미확인')}</td><td>{category.key==='open_orders'?`납기 ${r.due_date} · ${Number(r.order_qty).toLocaleString()} EA`:category.key==='quality_holds'?`ΔE ${r.delta_e??'미확인'} · ${r.appearance}`:category.key==='stock_issues'?`${Number(r.quantity).toLocaleString()} ${r.unit} / 안전재고 ${Number(r.safety_stock).toLocaleString()} ${r.unit}`:`예정 ${r.planned_date} · ${r.approval}`}</td><td><span className={'status '+(category.key==='open_orders'?'':'attention')}>{String(r.result||r.stock_status||r.status)}</span></td><td>{linkedLot?<button className="text-button" onClick={()=>onLot(linkedLot)}>LOT 보기<ArrowRight size={14}/></button>:<span className="muted">연결 LOT 없음</span>}</td></tr>;
 })}</tbody></table>{!filtered.length&&<p className="empty-note">조회된 첫 10개 레코드에는 해당 조건의 기록이 없습니다.</p>}</div>}
 <div className="operations-footer"><span>샘플 기준일 {workspace.meta.as_of} · 실제 운영 현황이 아닙니다.</span><span>조회 {new Date(workspace.meta.retrieved_at).toLocaleString('ko-KR')}</span></div>
 <DailyLogistics token={token} workspace={workspace} onAsk={onAsk}/>
 </section>;
}
