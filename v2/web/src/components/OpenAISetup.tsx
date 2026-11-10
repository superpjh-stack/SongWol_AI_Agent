import {useRef,useState} from 'react';
import {Mic,KeyRound} from 'lucide-react';
import {request,type Workspace} from '../types';

export default function OpenAISetup({token,workspace,onReady}:{token:string;workspace:Workspace;onReady:(startVoice:boolean)=>Promise<void>}){
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const form=useRef<HTMLFormElement>(null);
 const local=workspace.meta.access_required===false;
 return <section className="openai-setup"><h3><Mic size={18}/>음성 질의 · 답변</h3><p className="muted">질문을 말하면 송월 기록을 조회하고 음성으로 답합니다.<br/>{workspace.meta.realtime_model||'gpt-realtime-2.1'} · {workspace.meta.realtime_voice||'marin'}</p>
  {workspace.meta.ai_configured&&<><p className="connection-ready">서버 API 키가 연결되어 있습니다.</p><button className="primary" disabled={busy} onClick={()=>{setBusy(true);void onReady(true).catch(()=>{setError('화면 연결에 실패했습니다. 다시 시도하세요.');setBusy(false)})}}><Mic size={16}/>음성 대화 시작</button></>}
  {local?<form ref={form} onSubmit={async e=>{
   e.preventDefault();if(busy)return;const input=e.currentTarget;setBusy(true);setError('');
   const key=String(new FormData(input).get('api_key')||'');
   try{await request(token,'/settings/openai',{method:'POST',body:JSON.stringify({api_key:key})});input.reset();await onReady(true)}
   catch(reason){setError((reason as Error).message)}finally{input.reset();setBusy(false)}
  }}><label className="field-label"><span><KeyRound size={14}/> {workspace.meta.ai_configured?'API 키 변경':'OpenAI API 키'}</span><input aria-label="OpenAI API 키" name="api_key" type="password" autoComplete="off" placeholder="sk-…" required disabled={busy} maxLength={1027}/></label><p className="muted">키는 이 컴퓨터의 서버에만 저장합니다. 한 번 저장하면 다음에도 바로 사용할 수 있습니다.</p><button className="primary" disabled={busy}>{busy?'연결 확인 중…':'저장하고 음성 시작'}</button></form>:!workspace.meta.ai_configured&&<p className="warning">서버가 실행 중인 컴퓨터에서 API 키를 설정하세요.</p>}
  {error&&<p className="error" role="alert">{error}</p>}
 </section>;
}
