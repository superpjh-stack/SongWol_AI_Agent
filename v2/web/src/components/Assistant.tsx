import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {ArrowUp,Mic,MicOff,Plus,Square} from 'lucide-react';
import {request,type Message,type Workspace,type HistoryEntry} from '../types';
import {callsSongwol} from '../wake';
import {useRealtimeVoice} from '../hooks/useRealtimeVoice';
import {EvidenceRecord} from './Records';

export type AssistantHandle={ask:(text:string)=>void;reset:()=>void;startVoice:()=>void};
type Props={token:string;workspace:Workspace;lot:string;mode:string;onMode:(mode:string)=>void;active:boolean;onLot:(lot:string)=>void;onHistory:(entry:HistoryEntry)=>void;onBusy:(busy:boolean)=>void;onSettings:()=>void};
export default forwardRef<AssistantHandle,Props>(function Assistant({token,workspace,lot,mode:configuredMode,onMode:_onMode,active,onLot:_onLot,onHistory,onBusy,onSettings},ref){
 const mode=workspace.meta.ai_configured?'ai':'demo';
 void configuredMode;
 const [messages,setMessages]=useState<Message[]>([]),[question,setQuestion]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const epoch=useRef(0),pending=useRef<AbortController|null>(null),bottom=useRef<HTMLDivElement>(null);
 const voice=useRealtimeVoice(token,lot,turn=>setMessages(prev=>[...prev,{...turn,mode:'voice'}]),(_name,output)=>{try{const answer=JSON.parse(output);setMessages(prev=>[...prev,{...answer,role:'assistant',mode:'voice'}])}catch{/* Invalid output is not evidence. */}});
 const anchor=useRef(-1);
 useEffect(()=>{if(!active)return;const container=bottom.current?.parentElement;if(!container||!messages.length){anchor.current=-1;return}let user=-1;for(let i=messages.length-1;i>=0;i--){if(messages[i].role==='user'){user=i;break}}const answer=messages.findIndex((m,i)=>i>user&&m.role==='assistant');const index=answer>=0?answer:user;if(index<0||index===anchor.current)return;const target=container.querySelectorAll<HTMLElement>('.message')[index];if(target){anchor.current=index;container.scrollTo({top:Math.max(0,container.scrollTop+target.getBoundingClientRect().top-container.getBoundingClientRect().top-16),behavior:'instant'})}},[messages,active]);
 useEffect(()=>{if(!active)voice.stop()},[active,voice.stop]);
 useEffect(()=>{clear()},[lot]);
 useEffect(()=>{onBusy(busy||voice.active);return()=>onBusy(false)},[busy,voice.active,onBusy]);
 useEffect(()=>()=>{epoch.current++;pending.current?.abort()},[]);
 function clear(){epoch.current++;pending.current?.abort();pending.current=null;setBusy(false);setMessages([]);setError('');voice.stop()}
 async function ask(text:string){
  if(!callsSongwol(text)||pending.current||voice.active)return;
  setQuestion('');setError('');
  const run=epoch.current,controller=new AbortController();pending.current=controller;setBusy(true);
  const previous=messages;
  setMessages([...previous,{role:'user',text}]);onHistory({text,lot});
  try{
   const answer=await request<Message & {ignored?:boolean}>(token,'/chat',{method:'POST',signal:controller.signal,body:JSON.stringify({question:text,lot_id:lot||null,mode,history:previous.slice(-12).map(m=>({role:m.role,text:m.text}))})});
   if(run===epoch.current&&!answer.ignored)setMessages(prev=>[...prev,{...answer,role:'assistant'}]);
  }catch(e){if(run===epoch.current&&(e as Error).name!=='AbortError')setError((e as Error).message)}
  finally{if(run===epoch.current){setBusy(false);pending.current=null}}
 }
 useImperativeHandle(ref,()=>({ask:text=>{void ask(text)},reset:clear,startVoice:()=>{void voice.start()}}));
 const disabled=busy||voice.active;
 return (
<section className="assistant-content">
    <div className="chat-toolbar"><div><h1>송월 에이전트</h1><p>{workspace.meta.demo_data?'생산·품질·출하를 문서와 LOT 근거로 확인합니다.':'MES 원본 수주·재고·공정·생산 기록을 근거로 확인합니다.'}</p></div><button className="quiet-button" onClick={clear}><Plus size={16}/>새 대화</button></div>

    <div className="conversation" aria-live="polite">
     {!messages.length&&<div className="welcome simple-welcome"><h2>오늘 궁금한거 질문해!!</h2></div>}
     {messages.map((m,i)=><article key={i} className={'message '+m.role}><div className="message-label">{m.role==='user'?'나':m.mode==='voice'?'송월 · 음성':m.mode==='ai'?'송월 · AI 분석':'송월 · 자료 조회'}</div>{m.effective_lot&&<small>조회 LOT · {m.effective_lot}</small>}{m.comparison_tables?.map((t,ti)=><section className="comparison-table" key={ti}><h3>{t.title}</h3><div className="table-scroll" tabIndex={0} role="region" aria-label={t.title+' 비교표'}><table><thead><tr>{t.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{t.rows.map((r,ri)=><tr key={ri}>{r.map((v,ci)=><td key={ci}>{v}</td>)}</tr>)}</tbody></table></div></section>)}{m.comparison_tables?.length?<details><summary>분석 설명과 다음 확인사항</summary><div className="message-text">{m.text}</div></details>:<div className="message-text">{m.text}</div>}{m.request_coverage&&<details><summary>요청별 답변 확인</summary><ul>{m.request_coverage.map((c,ci)=><li key={ci}>{c.request} · {c.status==='answered'?'답변·근거 확인':'추가 확인 필요'}</li>)}</ul></details>}{!!m.evidence?.length&&<EvidenceRecord evidence={m.evidence}/>}{m.retrieved_at&&<small className="retrieved">조회 {new Date(m.retrieved_at).toLocaleString('ko-KR')}</small>}</article>)}
     {busy&&<div className="loading" role="status">자료를 확인하고 있습니다…</div>}<div ref={bottom}/>
    </div>
    <div className="composer-area">{error&&<div className="error" role="alert">{error}</div>}{mode==='ai'&&!workspace?.meta.ai_configured&&<p className="warning">AI 분석에는 서버 API 키 설정이 필요합니다. 데모 조회는 키 없이 사용할 수 있습니다.</p>}
     {voice.active&&<div className="voice-status"><span className="dot"/>음성 연결 · {voice.state}<button onClick={voice.toggleMute}>{voice.muted?<MicOff size={16}/>:<Mic size={16}/>} {voice.muted?'음소거 해제':'음소거'}</button><button onClick={voice.stop}><Square size={14}/>종료</button></div>}{voice.error&&<p className="error" role="alert">{voice.error}</p>}{voice.needsPlay&&<button onClick={voice.play}>음성 재생</button>}
     <form className="composer" onSubmit={e=>{e.preventDefault();void ask(question)}}><textarea aria-label="질문 입력" placeholder={lot?`${lot}의 상태를 알려줘`:'MES 수주·재고·품질에 대해 질문하세요…'} value={question} maxLength={4000} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void ask(question)}}}/><div className="composer-actions"><span>{mode==='demo'?'문서·DB 키워드 조회':'문서·DB 근거 기반 AI'}</span><button type="button" className="icon-button" aria-label="음성 시작" title="실시간 AI 음성" disabled={busy||voice.active} onClick={()=>{setError('');if(workspace.meta.ai_configured)void voice.start();else onSettings()}}><Mic size={19}/></button><button className="send" aria-label="질문 보내기" disabled={disabled||!callsSongwol(question)}><ArrowUp size={19}/></button></div></form><p className="composer-note">호출명 없이 편하게 질문하세요. 자료의 출처와 기준일은 조회 근거에서 확인하세요.</p>
    </div>
   </section>
 );
});
