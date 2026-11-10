import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {ArrowUp,Mic,MicOff,Plus,ChevronRight,Square} from 'lucide-react';
import {request,summaryLabels,type Message,type Workspace,type HistoryEntry} from '../types';
import {callsSongwol} from '../wake';
import {useRealtimeVoice} from '../hooks/useRealtimeVoice';
import {EvidenceRecord} from './Records';

export type AssistantHandle={ask:(text:string)=>void;reset:()=>void;startVoice:()=>void};
type Props={token:string;workspace:Workspace;lot:string;mode:string;onMode:(mode:string)=>void;active:boolean;onLot:(lot:string)=>void;onHistory:(entry:HistoryEntry)=>void;onBusy:(busy:boolean)=>void;onSettings:()=>void};
export default forwardRef<AssistantHandle,Props>(function Assistant({token,workspace,lot,mode,onMode,active,onLot,onHistory,onBusy,onSettings},ref){
 const [messages,setMessages]=useState<Message[]>([]),[question,setQuestion]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const epoch=useRef(0),pending=useRef<AbortController|null>(null),bottom=useRef<HTMLDivElement>(null);
 const voice=useRealtimeVoice(token,lot,turn=>setMessages(prev=>[...prev,{...turn,mode:'voice'}]));
 useEffect(()=>{if(!active)return;if(messages.length||busy)bottom.current?.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});else bottom.current?.parentElement?.scrollTo({top:0})},[messages,busy,active]);
 useEffect(()=>{if(!active)voice.stop()},[active,voice.stop]);
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
    <div className="chat-toolbar"><div><h1>송월아</h1><p>{workspace.meta.demo_data?'생산·품질·출하를 문서와 LOT 근거로 확인합니다.':'MES 원본 수주·재고·공정·생산 기록을 근거로 확인합니다.'}</p></div><button className="quiet-button" onClick={clear}><Plus size={16}/>새 대화</button></div>
    <div className="context-row"><label><span>조회 범위</span><select aria-label="조회 LOT" value={lot} onChange={e=>onLot(e.target.value)}><option value="">전체 기록</option>{workspace?.lots.map(l=><option key={l.print_lot} value={l.print_lot}>{l.print_lot}</option>)}</select></label><div className="mode-control"><button className={mode==='demo'?'selected':''} onClick={()=>{clear();onMode('demo')}}>데모 조회</button><button className={mode==='ai'?'selected':''} onClick={()=>{clear();onMode('ai')}}>AI 분석</button></div></div>
    <div className="conversation" aria-live="polite">
     {!messages.length&&<div className="welcome"><span className="eyebrow">SONGWOL · MANUFACTURING ASSISTANT</span><h2>주문부터 출하까지,<br/>기록으로 답합니다.</h2><p>인쇄 LOT, 품질검사, 재고와 출하.<br/>흩어진 기록을 한곳에서 확인하세요.</p><div className="kpis">{Object.entries(workspace.summary).map(([key,value])=><div key={key}><span>{summaryLabels[key]}</span><strong>{value}<small>건</small></strong></div>)}</div><div className="starter-label">이렇게 시작해 보세요</div><div className="starters">{(lot?['품질과 출하 상태를 알려줘','원단과 공정조건을 알려줘','색상 클레임 처리절차를 알려줘']:['오늘 재고현황을 알려줘','오늘 출하계획을 알려줘','내일 출하계획을 알려줘']).map(q=>'송월아, '+q).map(q=><button disabled={disabled} key={q} onClick={()=>ask(q)}>{q}<ChevronRight size={16}/></button>)}</div></div>}
     {messages.map((m,i)=><article key={i} className={'message '+m.role}><div className="message-label">{m.role==='user'?'나':m.mode==='voice'?'송월 · 음성':m.mode==='ai'?'송월 · AI 분석':'송월 · 데모 조회'}</div><div className="message-text">{m.text}</div>{!!m.evidence?.length&&<EvidenceRecord evidence={m.evidence}/>}{m.retrieved_at&&<small className="retrieved">조회 {new Date(m.retrieved_at).toLocaleString('ko-KR')}</small>}</article>)}
     {busy&&<div className="loading" role="status">자료를 확인하고 있습니다…</div>}<div ref={bottom}/>
    </div>
    <div className="composer-area">{error&&<div className="error" role="alert">{error}</div>}{mode==='ai'&&!workspace?.meta.ai_configured&&<p className="warning">AI 분석에는 서버 API 키 설정이 필요합니다. 데모 조회는 키 없이 사용할 수 있습니다.</p>}
     {voice.active&&<div className="voice-status"><span className="dot"/>음성 연결 · {voice.state}<button onClick={voice.toggleMute}>{voice.muted?<MicOff size={16}/>:<Mic size={16}/>} {voice.muted?'음소거 해제':'음소거'}</button><button onClick={voice.stop}><Square size={14}/>종료</button></div>}{voice.error&&<p className="error" role="alert">{voice.error}</p>}{voice.needsPlay&&<button onClick={voice.play}>음성 재생</button>}
     <form className="composer" onSubmit={e=>{e.preventDefault();void ask(question)}}><textarea aria-label="질문 입력" placeholder={lot?`송월아, ${lot}의 상태를 알려줘`:'송월아, MES 수주·재고 현황을 알려줘'} value={question} maxLength={4000} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void ask(question)}}}/><div className="composer-actions"><span>{mode==='demo'?'문서·DB 키워드 조회':'문서·DB 근거 기반 AI'}</span><button type="button" className="icon-button" aria-label="음성 시작" title="실시간 AI 음성" disabled={busy||voice.active} onClick={()=>{setError('');if(workspace.meta.ai_configured)void voice.start();else onSettings()}}><Mic size={19}/></button><button className="send" aria-label="질문 보내기" disabled={disabled||!callsSongwol(question)}><ArrowUp size={19}/></button></div></form><p className="composer-note">매 질문을 “송월아,”로 시작해 주세요. 이름을 부를 때만 답합니다. {mode==='demo'?'데모 조회는 AI 분석이 아닙니다.':'AI 답변은 원본 근거를 확인하세요.'} {workspace.meta.demo_data?'가상 자료 · 기존 LOT '+workspace.meta.as_of:'MES 원본 '+workspace.meta.as_of+' · '+workspace.meta.approval}</p>
    </div>
   </section>
 );
});
