import {useEffect,useState} from 'react';
import {BookOpen,Database,FileText,ChevronRight,Search} from 'lucide-react';
import {request,type Document,type Row,type Workspace} from '../types';
import Modal from './Modal';
import {RecordList} from './Records';

export default function ResourceLibrary({token,workspace,compact=false}:{token:string;workspace:Workspace;compact?:boolean}){
 const [tab,setTab]=useState('documents'),[search,setSearch]=useState(''),[table,setTable]=useState(workspace.meta.demo_data?'orders':'mes_orders');
 const [docs,setDocs]=useState<Document[]>([]),[rows,setRows]=useState<Row[]>([]),[doc,setDoc]=useState<Document|null>(null);
 const [day,setDay]=useState(workspace.meta.daily_anchor||'2026-10-09');
 const isDaily=['daily_inventory','shipment_plans','shipment_actuals'].includes(table);
 const [error,setError]=useState(''),[loading,setLoading]=useState(true),[retry,setRetry]=useState(0);
 useEffect(()=>{
  const controller=new AbortController();setLoading(true);setError('');setDocs([]);setRows([]);
  const path=tab==='documents'?'/documents?q='+encodeURIComponent(search):'/tables/'+table+(isDaily?'?business_date='+day:'');
  request<Document[]|Row[]>(token,path,{signal:controller.signal}).then(data=>{if(tab==='documents')setDocs(data as Document[]);else setRows(data as Row[])}).catch(e=>{if(!controller.signal.aborted)setError(e.message)}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});
  return()=>controller.abort();
 },[token,tab,search,table,day,retry]);
 return <section className={'resource-library '+(compact?'compact':'')}>
  {!compact&&<div className="page-heading"><span className="eyebrow">KNOWLEDGE & DATA</span><h1>문서와 원본 기록</h1><p>답변의 근거가 되는 문서와 제조 데이터를 확인하세요.</p></div>}
  <div className="tabs"><button className={tab==='documents'?'active':''} onClick={()=>setTab('documents')}><BookOpen size={16}/>지식베이스</button><button className={tab==='data'?'active':''} onClick={()=>setTab('data')}><Database size={16}/>데이터허브</button></div>
  {tab==='documents'?<label className="search"><Search size={16}/><input aria-label="문서 검색" placeholder="문서 이름, 내용 검색" value={search} onChange={e=>setSearch(e.target.value)}/></label>:<label className="field-label">조회 테이블<select aria-label="조회 테이블" value={table} onChange={e=>setTable(e.target.value)}>{Object.entries(workspace.tables).map(([key,value])=><option key={key} value={key}>{value}</option>)}</select></label>}
  {tab==='data'&&isDaily&&<label className="field-label daily-date">조회 날짜<input aria-label="자료 조회 날짜" type="date" min={workspace.meta.daily_start} max={workspace.meta.daily_end} value={day} onChange={e=>{if(e.target.value)setDay(e.target.value)}}/></label>}
  {loading?<p className="loading" role="status">자료를 불러오는 중…</p>:error?<div className="error" role="alert">{error}<button onClick={()=>setRetry(v=>v+1)}>다시 조회</button></div>:tab==='documents'?<><div className="section-label">참고 문서 <span>{docs.length}개 · 미승인 샘플</span></div><div className="documents">{docs.map(d=><button key={d.id} className="document" onClick={()=>setDoc(d)}><FileText size={18}/><span><strong>{d.title.replace(' (RAG 검증용 예시)','')}</strong><small>{d.revision} · 미승인 샘플</small></span><ChevronRight size={14}/></button>)}</div>{!docs.length&&<p className="empty-note">검색된 문서가 없습니다.</p>}</>:<><p className="muted">{isDaily?`${day} 전체 레코드 · EA · 가상 샘플`:'원본 첫 10개 레코드 · 읽기 전용'}</p><RecordList rows={rows}/></>}
  <p className="source-note">원본 기준일 {workspace.meta.as_of}<br/>{workspace.meta.demo_data?`일별 물류 ${workspace.meta.daily_start}~${workspace.meta.daily_end} · 가상 샘플`:'송월타월 MES 원본·자동 승인 아님'}<br/>실제 작업에는 승인 문서와 운영 기록을 확인하세요.</p>
  {doc&&<Modal title={doc.title} closeLabel="문서 닫기" onClose={()=>setDoc(null)}><p className="warning">{doc.revision} · {doc.approval}</p><div className="document-body">{doc.body}</div></Modal>}
 </section>;
}
