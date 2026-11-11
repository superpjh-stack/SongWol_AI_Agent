import {useEffect,useRef,useState,type ReactNode} from 'react';
import {BookOpen,History,MessageSquare,Plus,Settings,RefreshCw,X,Layers,LayoutGrid,ArrowUpRight} from 'lucide-react';
import type {View,Workspace,HistoryEntry} from '../types';

const views:{key:View;label:string;icon:typeof BookOpen}[]=[{key:'assistant',label:'대화',icon:MessageSquare},{key:'home',label:'현장',icon:LayoutGrid},{key:'lots',label:'LOT',icon:Layers},{key:'library',label:'자료',icon:BookOpen}];
type Props={view:View;lot:string;workspace:Workspace;history:HistoryEntry[];busy:boolean;refreshing:boolean;onNavigate:(view:View)=>void;onAsk:(q:string,lot?:string)=>void;onReset:()=>void;onSettings:()=>void;onRefresh:()=>void;resources:ReactNode;assistant:ReactNode;children:ReactNode};
export default function WorkspaceShell({view,lot,workspace,history,busy,refreshing,onNavigate,onAsk,onReset,onSettings,onRefresh,resources,assistant,children}:Props){
 const [panel,setPanel]=useState(''),[group,setGroup]=useState('');
 useEffect(()=>{if(!workspace.questions[group])setGroup(workspace.questions['MES 실데이터']?'MES 실데이터':Object.keys(workspace.questions)[0]||'')},[workspace,group]);
 const questionPanel=useRef<HTMLElement>(null),resourcePanel=useRef<HTMLElement>(null);
 useEffect(()=>{setPanel('')},[view]);
 useEffect(()=>{
  if(!panel)return;
  const previous=document.activeElement as HTMLElement|null;
  const region=panel==='questions'?questionPanel.current:resourcePanel.current;
  const focusable=()=>Array.from(region?.querySelectorAll<HTMLElement>('button:not(:disabled),input,select,summary,[tabindex="0"]')||[]).filter(el=>el.getClientRects().length);
  focusable()[0]?.focus();
  const keydown=(e:KeyboardEvent)=>{if(region?.querySelector('dialog[open]'))return;if(e.key==='Escape')setPanel('');if(e.key==='Tab'){const els=focusable(),first=els[0],last=els[els.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}};
  window.addEventListener('keydown',keydown);return()=>{window.removeEventListener('keydown',keydown);previous?.focus()};
 },[panel]);
 const ask=(text:string,context=lot)=>{setPanel('');onAsk(text,context)};
 return <div className="app">
  <header className="topbar"><a className="brand" href="#/assistant" aria-label="송월타월 대화 홈"><span className="brand-mark">S</span><span><strong>송월타월</strong><small>서울상사 · 제조 AI Agent</small></span></a><nav className="primary-nav" aria-label="주 메뉴">{views.map(v=><a key={v.key} href={`#/${v.key}${lot?'/'+encodeURIComponent(lot):''}`} aria-current={view===v.key?'page':undefined} onClick={e=>{e.preventDefault();onNavigate(v.key)}}><v.icon size={16}/>{v.label}</a>)}</nav><button className="icon-button refresh" aria-label="기록 새로고침" disabled={refreshing} onClick={onRefresh}><RefreshCw size={18}/></button><button className="icon-button" aria-label="설정" onClick={onSettings}><Settings size={19}/></button></header>
  {view==='assistant'&&<nav className="mobile-nav" aria-label="대화 보조 패널"><button onClick={()=>setPanel('questions')}><MessageSquare size={16}/>질문</button><span>{lot||'전체 기록'}</span><button onClick={()=>setPanel('resources')}><BookOpen size={16}/>자료</button></nav>}
  <div className={'layout '+(view==='assistant'?'chat-layout':'full-layout')}>
   {view==='assistant'&&<>{panel&&<button className="scrim" aria-label="패널 닫기" onClick={()=>setPanel('')}/>}
   <aside ref={questionPanel} className={'questions-panel '+(panel==='questions'?'open':'')} role={panel==='questions'?'dialog':undefined} aria-modal={panel==='questions'?true:undefined} aria-label="대화 도우미"><div className="panel-heading"><button className="mobile-close icon-button" aria-label="질문 닫기" onClick={()=>setPanel('')}><X size={18}/></button></div><button className="new-chat" onClick={()=>{setPanel('');onReset()}}><Plus size={16}/>새 대화 시작</button>
    <h3><MessageSquare size={16}/>추천질문리스트</h3><div className="tabs question-tabs">{Object.keys(workspace.questions).map(g=><button key={g} className={group===g?'active':''} onClick={()=>setGroup(g)}>{g}</button>)}</div><div className="suggestions">{workspace.questions[group]?.map((q,i)=><button disabled={busy} key={q} onClick={()=>ask(q,group==='재고·출하'?'':/PRT-[A-Z0-9-]+/i.exec(q)?.[0]||lot)}><span>{String(i+1).padStart(2,'0')}</span>{q}<ArrowUpRight size={13}/></button>)}</div>
    <h3 className="history-heading"><History size={16}/>최근 질문<span>{history.length}</span></h3><div className="history">{history.length?history.map((h,i)=><button key={i} disabled={busy} onClick={()=>ask(h.text,h.lot)}>{h.text}<small>{h.lot||'전체 기록'}</small></button>):<p className="muted">질문이 이곳에 기록됩니다.<br/>이전 질문과 LOT를 다시 불러오세요.</p>}</div><div className="panel-footer">기준일 {workspace.meta.as_of}<br/>{workspace.meta.demo_data?'가상 샘플·미승인':'원본 조회 데이터·자동 승인 아님'}</div>
   </aside></>}
   <main className={view==='assistant'?'chat-main':'page-main'} inert={panel?true:undefined}>
    <div className="assistant-mount" hidden={view!=='assistant'}>{assistant}</div>
    {children}
   </main>
   {view==='assistant'&&<aside ref={resourcePanel} className={'resources-panel '+(panel==='resources'?'open':'')} role={panel==='resources'?'dialog':undefined} aria-modal={panel==='resources'?true:undefined} aria-label="참고 자료"><div className="panel-heading"><span>참고 자료</span><button className="mobile-close icon-button" aria-label="자료 닫기" onClick={()=>setPanel('')}><X size={18}/></button></div>{resources}</aside>}
  </div>
 </div>;
}
