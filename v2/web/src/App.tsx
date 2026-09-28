import {useEffect,useRef,useState} from 'react';
import {ArrowUp,BookOpen,Database,History,MessageSquare,Mic,MicOff,Plus,Settings,X,ChevronRight,FileText,Headphones,Square} from 'lucide-react';
import type {Document,Message,Workspace} from './types';
import {useRealtimeVoice} from './hooks/useRealtimeVoice';

function stored<T>(key:string,fallback:T):T {try{return JSON.parse(sessionStorage.getItem(key)||'null')??fallback}catch{return fallback}}
function save(key:string,value:unknown){try{sessionStorage.setItem(key,JSON.stringify(value))}catch{/* Private browsing may disable storage. */}}
const labels:Record<string,string>={open_orders:'진행 주문',quality_holds:'품질 보류',stock_issues:'재고 주의',shipment_pending:'승인 대기'};
export default function App(){
 const [token,setToken]=useState(()=>stored('songwol-token','')),[workspace,setWorkspace]=useState<Workspace|null>(null),[error,setError]=useState('');
 const [docs,setDocs]=useState<Document[]>([]),[search,setSearch]=useState(''),[doc,setDoc]=useState<Document|null>(null),[table,setTable]=useState('orders'),[rows,setRows]=useState<Record<string,unknown>[]>([]);
 const [panel,setPanel]=useState(''),[tab,setTab]=useState('documents'),[settings,setSettings]=useState(false),[lot,setLot]=useState(''),[mode,setMode]=useState('demo');
 const [messages,setMessages]=useState<Message[]>([]),[question,setQuestion]=useState(''),[history,setHistory]=useState<{text:string;lot:string}[]>(()=>stored('songwol-history',[])),[busy,setBusy]=useState(false),[group,setGroup]=useState('생산·품질');
 const epoch=useRef(0),pending=useRef<AbortController|null>(null),bottom=useRef<HTMLDivElement>(null),dialog=useRef<HTMLDialogElement>(null),settingsDialog=useRef<HTMLDialogElement>(null);
 const voice=useRealtimeVoice(token,lot,turn=>setMessages(prev=>[...prev,{...turn,mode:'voice'}]));
 async function api(path:string,options:RequestInit={}){const r=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token,...options.headers}});const data=await r.json();if(!r.ok)throw Error(data.detail||'요청을 처리하지 못했습니다.');return data}
 useEffect(()=>{let alive=true;setWorkspace(null);setDocs([]);setRows([]);api('/workspace').then(data=>{if(alive){setWorkspace(data);setError('')}}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[token]);
 useEffect(()=>{if(!workspace)return;let alive=true;api('/documents?q='+encodeURIComponent(search)).then(data=>{if(alive)setDocs(data)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[workspace,search]);
 useEffect(()=>{if(!workspace)return;let alive=true;setRows([]);api('/tables/'+table).then(data=>{if(alive)setRows(data)}).catch(e=>{if(alive)setError(e.message)});return()=>{alive=false}},[workspace,table]);
 useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth'})},[messages,busy]);
 useEffect(()=>{if(doc)dialog.current?.showModal();else dialog.current?.close()},[doc]);
 useEffect(()=>{if(settings)settingsDialog.current?.showModal();else settingsDialog.current?.close()},[settings]);
 useEffect(()=>()=>{pending.current?.abort()},[]);
 function clear(){epoch.current++;pending.current?.abort();pending.current=null;setBusy(false);setMessages([]);setError('');voice.stop()}
 function changeLot(value:string){clear();setLot(value)}
 async function ask(text:string,selectedLot=lot){
  if(!text.trim()||busy||voice.active)return;
  setPanel('');setQuestion('');setError('');
  const previous=selectedLot===lot?messages:[];
  if(selectedLot!==lot){clear();setLot(selectedLot)}
  const run=epoch.current,controller=new AbortController();pending.current=controller;setBusy(true);
  setMessages([...previous,{role:'user',text}]);
  const next=[{text,lot:selectedLot},...history.filter(h=>h.text!==text||h.lot!==selectedLot)].slice(0,20);setHistory(next);save('songwol-history',next);
  try{const answer=await api('/chat',{method:'POST',signal:controller.signal,body:JSON.stringify({question:text,lot_id:selectedLot||null,mode,history:previous.slice(-12).map(m=>({role:m.role,text:m.text}))})});if(run===epoch.current)setMessages(prev=>[...prev,{role:'assistant',...answer}])}
  catch(e){if(run===epoch.current&&(e as Error).name!=='AbortError')setError((e as Error).message)}finally{if(run===epoch.current){setBusy(false);pending.current=null}}
 }
 const disabled=busy||voice.active||!workspace;
 return <div className="app">
  <header className="topbar"><div className="brand-mark">S</div><div className="brand"><strong>송월타월</strong><span>서울상사 · AI Agent</span></div><div className="header-note"><span className="dot"/> 제조 지식 워크스페이스</div><span className="sample-tag">샘플 데이터</span><button className="icon-button" aria-label="설정" onClick={()=>setSettings(true)}><Settings size={19}/></button></header>
  <nav className="mobile-nav"><button onClick={()=>setPanel(panel==='left'?'':'left')}><BookOpen size={16}/>자료</button><button onClick={()=>setPanel(panel==='right'?'':'right')}><MessageSquare size={16}/>질문</button></nav>
  <div className="layout">
   {panel&&<button className="scrim" aria-label="패널 닫기" onClick={()=>setPanel('')}/>}
   <aside className={'left-panel '+(panel==='left'?'open':'')}>
    <div className="panel-heading"><span>WORKSPACE</span><button className="mobile-close icon-button" aria-label="자료 닫기" onClick={()=>setPanel('')}><X size={18}/></button></div>
    <div className="tabs"><button className={tab==='documents'?'active':''} onClick={()=>setTab('documents')}><BookOpen size={16}/>지식베이스</button><button className={tab==='data'?'active':''} onClick={()=>setTab('data')}><Database size={16}/>데이터허브</button></div>
    {tab==='documents'?<><label className="search"><input aria-label="문서 검색" placeholder="문서 검색" value={search} onChange={e=>setSearch(e.target.value)}/></label><div className="section-label">참고 문서 <span>{docs.length}</span></div><div className="documents">{docs.map(d=><button key={d.id} className="document" onClick={()=>setDoc(d)}><FileText size={18}/><span><strong>{d.title.replace(' (RAG 검증용 예시)','')}</strong><small>{d.revision} · 미승인 샘플</small></span><ChevronRight size={14}/></button>)}{workspace&&!docs.length&&<p className="muted">검색된 문서가 없습니다.</p>}</div><div className="source-note"><BookOpen size={18}/><p>답변의 시작은 근거에서<br/><span>문서 개정과 원본 기록을<br/>함께 확인하세요.</span></p></div></>:<><label className="field-label">조회 테이블<select aria-label="조회 테이블" value={table} onChange={e=>setTable(e.target.value)}>{Object.entries(workspace?.tables||{}).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label><p className="muted">원본 첫 10개 레코드 · 읽기 전용</p><div className="record-list">{rows.map((r,i)=><details key={i}><summary>{String(Object.values(r)[0])}</summary><dl>{Object.entries(r).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{String(v??'미확인')}</dd></div>)}</dl></details>)}</div></>}
    <div className="panel-footer"><span className="dot"/> SQLite 샘플 · 2026.09.03 기준</div>
   </aside>
   <main>
    <div className="chat-toolbar"><div><h1>송월타월 AI Agent</h1><p>한 올의 품질부터, 고객에게 닿는 순간까지.</p></div><button className="quiet-button" onClick={clear}><Plus size={16}/>새 대화</button></div>
    <div className="context-row"><label><span>조회 범위</span><select aria-label="조회 LOT" value={lot} onChange={e=>changeLot(e.target.value)}><option value="">전체 기록</option>{workspace?.lots.map(l=><option key={l.print_lot} value={l.print_lot}>{l.print_lot}</option>)}</select></label><div className="mode-control"><button className={mode==='demo'?'selected':''} onClick={()=>{clear();setMode('demo')}}>데모 조회</button><button className={mode==='ai'?'selected':''} onClick={()=>{clear();setMode('ai')}}>AI 분석</button></div></div>
    <div className="conversation" aria-live="polite">
     {!messages.length&&<div className="welcome"><span className="eyebrow">SONGWOL INTELLIGENCE</span><h2>오늘의 제조 현황,<br/>무엇이 궁금하신가요?</h2><p>인쇄 LOT, 품질검사, 재고와 출하.<br/>흩어진 기록을 한곳에서 확인하세요.</p><div className="kpis">{Object.entries(workspace?.summary||{}).map(([key,value])=><div key={key}><span>{labels[key]}</span><strong>{value}<small>건</small></strong></div>)}</div><div className="starter-label">이렇게 시작해 보세요</div><div className="starters">{['품질 보류 LOT를 보여줘','안전재고 미달 품목을 알려줘','색상 클레임 처리절차를 알려줘'].map(q=><button disabled={disabled} key={q} onClick={()=>ask(q)}>{q}<ChevronRight size={16}/></button>)}</div></div>}
     {messages.map((m,i)=><article key={i} className={'message '+m.role}><div className="message-label">{m.role==='user'?'나':m.mode==='voice'?'송월 AI · 음성':m.mode==='ai'?'송월 AI · AI 분석':'송월 AI · 데모 조회'}</div><div className="message-text">{m.text}</div>{!!m.evidence?.length&&<details className="evidence"><summary>조회 근거 {m.evidence.length}개</summary>{m.evidence.map((e,j)=><details key={j}><summary>{e.kind==='document'?'문서':'원본 레코드'} · {e.title}</summary><p>{e.source} · 가상 샘플</p><pre>{JSON.stringify(e.result??{error:e.error},null,2)}</pre></details>)}</details>}{m.retrieved_at&&<small className="retrieved">조회 {new Date(m.retrieved_at).toLocaleString('ko-KR')}</small>}</article>)}
     {busy&&<div className="loading" role="status">자료를 확인하고 있습니다…</div>}<div ref={bottom}/>
    </div>
    <div className="composer-area">{error&&<div className="error" role="alert">{error}</div>}{mode==='ai'&&!workspace?.meta.ai_configured&&<p className="warning">AI 분석에는 서버 API 키 설정이 필요합니다. 데모 조회는 키 없이 사용할 수 있습니다.</p>}
     {voice.active&&<div className="voice-status"><span className="dot"/>음성 연결 · {voice.state}<button onClick={voice.toggleMute}>{voice.muted?<MicOff size={16}/>:<Mic size={16}/>} {voice.muted?'음소거 해제':'음소거'}</button><button onClick={voice.stop}><Square size={14}/>종료</button></div>}{voice.error&&<p className="error" role="alert">{voice.error}</p>}{voice.needsPlay&&<button onClick={voice.play}>음성 재생</button>}
     <form className="composer" onSubmit={e=>{e.preventDefault();void ask(question)}}><textarea aria-label="질문 입력" placeholder={lot?`${lot}에 대해 질문하세요`:'주문, 인쇄 LOT 또는 문서에 대해 질문하세요'} value={question} maxLength={4000} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void ask(question)}}}/><div className="composer-actions"><span>{mode==='demo'?'문서·DB 키워드 조회':'문서·DB 근거 기반 AI'}</span><button type="button" className="icon-button" aria-label="음성 시작" title="실시간 AI 음성" disabled={busy||voice.active||!workspace?.meta.ai_configured} onClick={()=>{setError('');void voice.start()}}><Mic size={19}/></button><button className="send" aria-label="질문 보내기" disabled={disabled||!question.trim()}><ArrowUp size={19}/></button></div></form><p className="composer-note">{mode==='demo'?'데모 조회는 AI 분석이 아닙니다.':'AI 답변은 원본 근거를 확인하세요.'} 샘플 자료로 실제 출하를 승인하지 않습니다.</p>
    </div>
   </main>
   <aside className={'right-panel '+(panel==='right'?'open':'')}><div className="panel-heading"><span>대화 도우미</span><button className="mobile-close icon-button" aria-label="질문 닫기" onClick={()=>setPanel('')}><X size={18}/></button></div><h3><History size={16}/>최근 질문 <span>{history.length}</span></h3><div className="history">{history.length?history.map((h,i)=><button disabled={disabled} key={i} onClick={()=>ask(h.text,h.lot)}>{h.text}<small>{h.lot||'전체 기록'}</small></button>):<p className="muted">질문하면 이곳에 기록됩니다.<br/>이전 질문을 다시 확인해 보세요.</p>}</div><h3><MessageSquare size={16}/>추천 질문</h3><div className="tabs question-tabs">{['생산·품질','문서·규칙'].map(g=><button key={g} className={group===g?'active':''} onClick={()=>setGroup(g)}>{g}</button>)}</div><div className="suggestions">{workspace?.questions[group]?.map((q,i)=><button disabled={disabled} onClick={()=>ask(q)} key={q}><span>{String(i+1).padStart(2,'0')}</span>{q}</button>)}</div><div className="help-note"><Headphones size={18}/><span>현장에서는 음성으로<br/><small>서버 AI 설정 후 사용 가능</small></span></div></aside>
  </div>
  <dialog ref={dialog} onCancel={()=>setDoc(null)}><div className="dialog-heading"><h2>{doc?.title}</h2><button className="icon-button" aria-label="문서 닫기" onClick={()=>setDoc(null)}><X/></button></div><p className="warning">{doc?.revision} · {doc?.approval}</p><div className="document-body">{doc?.body}</div></dialog>
  <dialog ref={settingsDialog} onCancel={()=>setSettings(false)}><div className="dialog-heading"><h2>연결 설정</h2><button className="icon-button" aria-label="설정 닫기" onClick={()=>setSettings(false)}><X/></button></div><p>API 키는 서버에서 관리합니다. 이곳에는 서버에 설정된 접근 코드만 입력하세요.</p><form onSubmit={e=>{e.preventDefault();const value=String(new FormData(e.currentTarget).get('token')||'');clear();setToken(value);save('songwol-token',value);setSettings(false)}}><label className="field-label">AI 접근 코드<input name="token" type="password" autoComplete="off" defaultValue={token} key={String(settings)}/></label><p className="muted">접근 코드와 질문 이력은 이 탭의 세션에만 저장됩니다.</p><button className="primary">설정 저장</button></form></dialog>
 </div>
}
