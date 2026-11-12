import {useCallback,useEffect,useRef,useState} from 'react';
import {Settings,RefreshCw} from 'lucide-react';
import {request,stored,save,ApiError,type Workspace,type HistoryEntry,type View} from './types';
import TowelStudio from './components/TowelStudio';
import ReportPanel from './components/ReportPanel';
import Assistant,{type AssistantHandle} from './components/Assistant';
import WorkspaceShell from './components/WorkspaceShell';
import ResourceLibrary from './components/ResourceLibrary';
import LotWorkspace from './components/LotWorkspace';
import OperationsHome from './components/OperationsHome';
import Modal from './components/Modal';
import OpenAISetup from './components/OpenAISetup';
import {loadAccessCode,rememberAccessCode,forgetAccessCode} from './accessCode';

function readRoute(){
 const [raw,encoded]=location.hash.replace(/^#\/?/,'').split('/');
 const view:View=['assistant','home','lots','library','studio','reports'].includes(raw)?raw as View:'assistant';
 try{return {view,lot:encoded?decodeURIComponent(encoded):''}}catch{return {view:'assistant' as View,lot:''}}
}
export default function App(){
 const [route,setRoute]=useState(readRoute),[token,setToken]=useState(loadAccessCode);
 const [workspace,setWorkspace]=useState<Workspace|null>(null),[error,setError]=useState(''),[settings,setSettings]=useState(()=>new URLSearchParams(location.search).get('setup')==='openai'),[refresh,setRefresh]=useState(0),[refreshing,setRefreshing]=useState(false);
 const [voiceRequested,setVoiceRequested]=useState(false);
 const [storageWarning,setStorageWarning]=useState('');
 const [mode,setMode]=useState('demo');
 const [busy,setBusy]=useState(false),[history,setHistory]=useState<HistoryEntry[]>(()=>{const value=stored<unknown>('songwol-history',[]);return Array.isArray(value)?value.filter((h):h is HistoryEntry=>typeof h?.text==='string'&&typeof h?.lot==='string').slice(0,20):[]});
 const assistant=useRef<AssistantHandle>(null);
 const [queued,setQueued]=useState<{text:string;lot:string}|null>(null);
 useEffect(()=>{const update=()=>setRoute(readRoute());window.addEventListener('hashchange',update);if(!location.hash)window.history.replaceState(null,'','#/assistant');return()=>window.removeEventListener('hashchange',update)},[]);
 useEffect(()=>{
  const controller=new AbortController();setError('');setRefreshing(true);
  request<Workspace>(token,'/workspace',{signal:controller.signal}).then(data=>{if(controller.signal.aborted)return;setWorkspace(data);setStorageWarning(data.meta.access_required===false||rememberAccessCode(token)?'':'브라우저가 코드 저장을 차단했습니다. 현재 접속은 유지되지만 다시 열면 입력이 필요합니다.')} ).catch(e=>{if(!controller.signal.aborted){setError(e.message);if(e instanceof ApiError&&e.status===401){setWorkspace(null);setSettings(true)}}}).finally(()=>{if(!controller.signal.aborted)setRefreshing(false)});
  return()=>controller.abort();
 },[token,refresh]);
 const navigate=(view:View,lot=route.lot)=>{setRoute({view,lot});const target=`#/${view}${lot?'/'+encodeURIComponent(lot):''}`;if(location.hash!==target)location.hash=target};
 const ask=(text:string,lot=route.lot)=>{if(route.view==='assistant'&&lot===route.lot){assistant.current?.ask(text)}else{if(busy)assistant.current?.reset();setQueued({text,lot});navigate('assistant',lot)}};
 useEffect(()=>{if(queued&&workspace&&route.view==='assistant'&&route.lot===queued.lot&&assistant.current){assistant.current.ask(queued.text);setQueued(null)}},[queued,workspace,route]);
 const remember=useCallback((entry:HistoryEntry)=>{setHistory(previous=>{const next=[entry,...previous.filter(h=>h.text!==entry.text||h.lot!==entry.lot)].slice(0,20);save('songwol-history',next);return next})},[]);
 function applyAccessCode(value:string){
  assistant.current?.reset();setQueued(null);setWorkspace(null);setError('');setStorageWarning('');setBusy(false);setToken(value);setRefresh(v=>v+1);setSettings(false);
 }
 useEffect(()=>{if(voiceRequested&&workspace?.meta.ai_configured&&route.view==='assistant'&&assistant.current){setVoiceRequested(false);assistant.current.startVoice()}},[voiceRequested,workspace,route]);
 const connection=settings&&(workspace||error)&&<Modal title="연결 설정" closeLabel="설정 닫기" onClose={()=>setSettings(false)}>
  {workspace&&<OpenAISetup token={token} workspace={workspace} onReady={async startVoice=>{
   const data=await request<Workspace>(token,'/workspace');setWorkspace(data);setSettings(false);navigate('assistant');setVoiceRequested(startVoice);
  }}/>}
  {workspace?.meta.access_required===false?<p className="muted">이 컴퓨터에서는 자동으로 연결됩니다.</p>:<>
  <p>접근 코드를 처음 한 번 입력하면 이 브라우저에서 자동으로 연결합니다.</p>
  {error&&<p className="error" role="alert">{error}</p>}
  <form onSubmit={e=>{e.preventDefault();applyAccessCode(String(new FormData(e.currentTarget).get('token')||''))}}>
   <label className="field-label">접근 코드<input name="token" type="password" autoComplete="off" defaultValue={token}/></label>
   <p className="muted">탭이나 브라우저를 닫아도 기억합니다. OpenAI API 키는 서버에서만 관리합니다.</p>
   <button className="primary">설정 저장</button>
   {token&&<button type="button" className="quiet-button" onClick={()=>{forgetAccessCode();applyAccessCode('')}}>저장된 코드 지우기</button>}
  </form></>}
 </Modal>;
 if(!workspace)return <div className="state-page"><span className="brand-mark">S</span><h1>송월타월 제조 AI Agent</h1>{error?<><p className="error" role="alert">{error}</p><div className="state-actions"><button className="primary" onClick={()=>setRefresh(v=>v+1)}><RefreshCw size={16}/>다시 연결</button><button className="quiet-button" onClick={()=>setSettings(true)}><Settings size={16}/>연결 설정</button></div></>:<p role="status">제조 기록을 준비하고 있습니다…</p>}{connection}</div>;
 return <><WorkspaceShell view={route.view} lot={route.lot} workspace={workspace} history={history} busy={busy} refreshing={refreshing} onNavigate={view=>{setQueued(null);navigate(view)}} onAsk={ask} onReset={()=>assistant.current?.reset()} onSettings={()=>setSettings(true)} onRefresh={()=>setRefresh(v=>v+1)} resources={<ResourceLibrary key={refresh} token={token} workspace={workspace} compact/>} assistant={<Assistant key={token+'|'+route.lot} ref={assistant} token={token} workspace={workspace} mode={mode} onMode={setMode} lot={route.lot} active={route.view==='assistant'} onLot={lot=>{setQueued(null);navigate('assistant',lot)}} onHistory={remember} onBusy={setBusy} onSettings={()=>setSettings(true)}/>}>
  {storageWarning&&<p className="warning" role="status">{storageWarning}</p>}
  {error&&<div className="error refresh-error" role="alert">새로고침에 실패했습니다. 기존 조회 결과를 표시합니다. {error}<button onClick={()=>setRefresh(v=>v+1)}>다시 조회</button></div>}
  {route.view==='studio'&&<TowelStudio key={token} token={token} workspace={workspace}/>}
  {route.view==='reports'&&<ReportPanel key={token} token={token} mes={!workspace.meta.demo_data}/>}
  {route.view==='home'&&<OperationsHome key={refresh} token={token} workspace={workspace} onLot={lot=>navigate('lots',lot)} onAsk={ask}/>}
  {route.view==='lots'&&<LotWorkspace key={refresh} token={token} workspace={workspace} lot={route.lot} onSelect={lot=>navigate('lots',lot)} onAsk={ask}/>}
  {route.view==='library'&&<ResourceLibrary key={refresh} token={token} workspace={workspace}/>}
 </WorkspaceShell>{connection}</>;
}
