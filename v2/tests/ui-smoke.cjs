// PLAYWRIGHT_MODULE can point to an existing local Playwright installation.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 await require('./access-code.cjs')(browser);
 const page=await browser.newPage({viewport:{width:1440,height:960}});
 page.setDefaultTimeout(12000);
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8513');
 await page.getByRole('button',{name:'원단·인쇄 LOT 추적 SOP'}).waitFor();
 // The real local server must open without credentials, including stale browser codes.
 assert.equal(await page.locator('dialog[open]').count(),0);
 assert.equal(await page.getByRole('button',{name:'다시 연결',exact:true}).count(),0);
 await page.evaluate(()=>localStorage.setItem('songwol-token',JSON.stringify('outdated-test-code')));
 await page.reload();
 await page.getByRole('button',{name:'원단·인쇄 LOT 추적 SOP'}).waitFor();
 assert.equal(await page.locator('dialog[open]').count(),0);
 await page.getByRole('button',{name:'설정',exact:true}).click();
 await page.getByText('이 컴퓨터에서는 자동으로 연결됩니다.',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('접근 코드',{exact:true}).count(),0);
 await page.getByRole('button',{name:'설정 닫기',exact:true}).click();

 await page.screenshot({path:'artifacts/desktop.png',fullPage:true});
 await page.getByLabel('문서 검색').fill('클레임');
 await page.getByRole('button',{name:'클레임 대응 매뉴얼'}).click();
 assert.match(await page.locator('dialog[open]').innerText(),/미승인/);
 await page.getByLabel('문서 닫기',{exact:true}).click();
 await page.getByRole('button',{name:'데이터허브',exact:true}).click();
 await page.getByLabel('조회 테이블').selectOption('lot_quality');
 await page.locator('summary').filter({hasText:'QI-260903'}).click();
 await page.getByText('4.7',{exact:true}).waitFor();
 await page.getByRole('button',{name:'AI 분석',exact:true}).click();
 await page.getByLabel('조회 LOT').selectOption('PRT-260903-C');
 assert.equal(await page.locator('.mode-control .selected').innerText(),'AI 분석');
 await page.getByRole('button',{name:'데모 조회',exact:true}).click();
 await page.getByLabel('질문 입력').fill('오늘 재고 알려줘');
 assert.equal(await page.getByLabel('질문 보내기').isDisabled(),true);
 await page.getByLabel('질문 입력').press('Enter');
 assert.equal(await page.locator('.message').count(),0);
 await page.getByLabel('질문 입력').fill('송월아, 품질과 출하 상태');
 await page.getByLabel('질문 보내기').click();
 await page.locator('.message.assistant').waitFor();
 assert.match(await page.locator('.message.assistant').innerText(),/보류/);
 await page.getByText('조회 근거 2개',{exact:true}).click();
 await page.getByText('원본 레코드 · trace_lot',{exact:true}).click();
 assert.match(await page.locator('.evidence pre').first().innerText(),/QI-260903/);
 await page.screenshot({path:'artifacts/desktop-answer.png',fullPage:true});
 await page.getByRole('button',{name:'새 대화',exact:true}).click();
 assert.equal(await page.locator('.message').count(),0);
 await page.locator('.history button').first().click();
 await page.locator('.message.assistant').waitFor();
 // Abort an in-flight response by changing LOT.
 await page.route('**/api/chat',async route=>{await new Promise(r=>setTimeout(r,700));try{await route.fulfill({json:{text:'STALE-ANSWER',mode:'demo',evidence:[]}})}catch{}});
 await page.getByLabel('질문 입력').fill('송월아, 늦은 응답 테스트');
 await page.getByLabel('질문 보내기').click();
 await page.getByLabel('조회 LOT').selectOption('PRT-260901-A');
 await page.waitForTimeout(900);
 assert.equal(await page.locator('.message').count(),0);
 await page.unroute('**/api/chat');
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'artifacts/mobile.png',fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.getByRole('button',{name:'자료',exact:true}).click();
 await page.getByRole('button',{name:'지식베이스',exact:true}).click();
 await page.getByLabel('문서 검색').fill('품질');
 await page.getByRole('button',{name:'인쇄 품질 기준서'}).click();
 assert.match(await page.locator('dialog[open]').innerText(),/QC-PRINT-R3/);
 await page.getByLabel('문서 닫기',{exact:true}).click();
 await page.getByLabel('자료 닫기',{exact:true}).click();
 await page.getByRole('button',{name:'질문',exact:true}).click();
 await page.getByRole('button',{name:'문서·규칙',exact:true}).click();
 await page.getByRole('button',{name:'01 송월아, 인쇄 품질 기준서의 검사 기록 항목을 알려줘'}).click();
 await page.locator('.message.assistant').waitFor();
 await page.screenshot({path:'artifacts/mobile-answer.png',fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.deepEqual(errors,[]);

 // Cross-screen flows use the existing API and preserve LOT context.
 await page.setViewportSize({width:1440,height:960});
 const menu=page.getByRole('navigation',{name:'주 메뉴',exact:true});
 await menu.getByRole('link',{name:'현장',exact:true}).click();
 await page.getByRole('heading',{name:'현장의 기록을 한눈에.'}).waitFor();
 await page.locator('.overview-kpis button').filter({hasText:'품질 보류'}).click();
 await page.locator('tbody tr').filter({hasText:'QI-260903'}).waitFor();
 assert.equal(await page.locator('tbody tr').count(),2);
 await page.screenshot({path:'artifacts/operations-desktop.png',fullPage:true});
 await page.locator('tbody tr').filter({hasText:'QI-260903'}).getByRole('button',{name:'LOT 보기'}).click();
 await page.getByRole('heading',{name:'PRT-260903-C',exact:true}).waitFor();
 await page.locator('.trace-section').filter({has:page.getByRole('heading',{name:/품질검사/})}).locator('summary').filter({hasText:'QI-260903'}).click();
 assert.match(await page.locator('.lot-detail').innerText(),/4.7/);
 await page.screenshot({path:'artifacts/lot-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'이 LOT로 질문',exact:true}).click();
 await page.locator('.message.assistant').waitFor();
 assert.equal(await page.getByLabel('조회 LOT').inputValue(),'PRT-260903-C');
 assert.match(await page.locator('.message.assistant').innerText(),/보류/);
 await page.goBack();
 await page.getByRole('heading',{name:'PRT-260903-C',exact:true}).waitFor();
 await page.goForward();
 await page.locator('.message.assistant').waitFor();
 // The mounted chat remains intact when navigating to resources and back.
 const answer=await page.locator('.message.assistant').innerText();
 await menu.getByRole('link',{name:'자료',exact:true}).click();
 await page.getByRole('heading',{name:'문서와 원본 기록'}).waitFor();
 await page.getByLabel('문서 검색').fill('존재하지않는문서XYZ');
 await page.getByText('검색된 문서가 없습니다.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'데이터허브',exact:true}).click();
 await page.getByLabel('조회 테이블').selectOption('shipments');
 await page.locator('.record-list details').first().waitFor();
 assert.equal(await page.locator('.record-list details').count(),10);
 await page.screenshot({path:'artifacts/library-desktop.png',fullPage:true});
 await menu.getByRole('link',{name:'대화',exact:true}).click();
 assert.equal(await page.locator('.message.assistant').innerText(),answer);
 // Failed resources show an error and support retry, never a false empty result.
 let tableFailure=true;
 await page.route('**/api/tables/orders',route=>tableFailure?route.fulfill({status:503,json:{detail:'테스트 자료 연결 실패'}}):route.continue());
 await menu.getByRole('link',{name:'자료',exact:true}).click();
 await page.getByRole('button',{name:'데이터허브',exact:true}).click();
 await page.getByText('테스트 자료 연결 실패',{exact:false}).waitFor();
 tableFailure=false;
 await page.getByRole('button',{name:'다시 조회',exact:true}).click();
 await page.locator('.record-list details').first().waitFor();
 await page.unroute('**/api/tables/orders');
 // Mobile dedicated views and keyboard dismissal of supplementary panels.
 await page.setViewportSize({width:390,height:844});
 for(const name of ['현장','LOT','자료']){
  await menu.getByRole('link',{name,exact:true}).click();
  await page.waitForTimeout(150);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${name} must not overflow`);
  await page.screenshot({path:`artifacts/${name==='현장'?'operations':name==='LOT'?'lot':'library'}-mobile.png`,fullPage:true});
 }
 await menu.getByRole('link',{name:'LOT',exact:true}).click();
 await page.getByLabel('LOT 검색').fill('없는LOT');
 await page.getByText('일치하는 LOT가 없습니다.',{exact:true}).waitFor();
 await menu.getByRole('link',{name:'대화',exact:true}).click();
 await page.getByRole('button',{name:'질문',exact:true}).click();
 await page.keyboard.press('Escape');
 assert.equal(await page.getByRole('dialog',{name:'대화 도우미'}).count(),0);
 assert.equal(await page.evaluate(()=>document.activeElement.textContent),'질문');
 await page.getByRole('button',{name:'새 대화',exact:true}).click();
 await page.screenshot({path:'artifacts/mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);

 // Dated logistics recommendations clear unrelated LOT context and use the new data.
 await page.setViewportSize({width:1440,height:960});
 await page.getByRole('button',{name:'재고·출하',exact:true}).click();
 assert.equal(await page.locator('.suggestions button').count(),10);
 await page.locator('.suggestions button').filter({hasText:'오늘 재고현황'}).click();
 await page.locator('.message.assistant').waitFor();
 assert.equal(await page.getByLabel('조회 LOT').inputValue(),'');
 assert.match(await page.locator('.message.assistant').last().innerText(),/재고 스냅샷/);
 await page.getByRole('button',{name:'새 대화',exact:true}).click();
 await page.locator('.suggestions button').filter({hasText:'앞으로 15일 출하계획'}).click();
 await page.locator('.message.assistant').waitFor();
 assert.match(await page.locator('.message.assistant').innerText(),/2026-10-10~2026-10-24/);
 assert.match(await page.locator('.message.assistant').innerText(),/미래 실적 없음/);
 await page.screenshot({path:'artifacts/logistics-answer-desktop.png',fullPage:true});
 await menu.getByRole('link',{name:'자료',exact:true}).click();
 await page.getByRole('button',{name:'데이터허브',exact:true}).click();
 await page.getByLabel('조회 테이블').selectOption('shipment_plans');
 await page.getByLabel('자료 조회 날짜').fill('2026-10-24');
 await page.locator('.record-list summary').filter({hasText:'DEMO-SP-261024-01'}).waitFor();
 assert.equal(await page.locator('.record-list details').count(),4);
 await page.getByLabel('조회 테이블').selectOption('shipment_actuals');
 await page.getByText('연결된 기록이 없습니다.',{exact:true}).waitFor();
 await page.getByLabel('자료 조회 날짜').fill('2026-09-24');
 await page.locator('.record-list summary').filter({hasText:'DEMO-OUT-260924-01'}).waitFor();
 assert.equal(await page.locator('.record-list details').count(),2);
 await menu.getByRole('link',{name:'현장',exact:true}).click();
 const logistics=page.locator('.daily-logistics');
 await page.getByLabel('물류 조회 날짜').fill('2026-10-24');
 await logistics.getByRole('button',{name:'출하계획',exact:true}).click();
 await logistics.locator('summary').filter({hasText:'DEMO-SP-261024-01'}).waitFor();
 await logistics.scrollIntoViewIfNeeded();
 await page.screenshot({path:'artifacts/logistics-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await logistics.scrollIntoViewIfNeeded();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.screenshot({path:'artifacts/logistics-mobile.png',fullPage:true});
 await logistics.getByRole('button',{name:'이 날짜로 질문',exact:true}).click();
 await page.locator('.message.assistant').waitFor();
 assert.match(await page.locator('.message.assistant').last().innerText(),/2026-10-24/);
 assert.deepEqual(errors,[]);

 // Mock media and the provider boundary: no microphone or paid AI call is used.
 await page.addInitScript(()=>{
  window.__voice={stopped:0,closed:0,deny:false,sent:[]};
  const track={enabled:true,stop(){window.__voice.stopped++}};
  window.__voice.track=track;
  Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>{
   if(window.__voice.deny)throw new DOMException('denied','NotAllowedError');
   return {getTracks:()=>[track],getAudioTracks:()=>[track]};
  }});
  window.RTCPeerConnection=class {
   connectionState='new';
   constructor(){window.__voice.peer=this}
   addTrack(){} async createOffer(){return {type:'offer',sdp:'mock-offer'}}
   async setLocalDescription(){} async setRemoteDescription(){this.connectionState='connected';this.onconnectionstatechange?.();this.dc.readyState='open';this.dc.onopen?.()}
   createDataChannel(){this.dc={readyState:'connecting',close(){},send(raw){window.__voice.sent.push(JSON.parse(raw))}};window.__voice.dc=this.dc;return this.dc}
   close(){window.__voice.closed++}
  };
 });
 await page.route('**/api/workspace',async route=>{const response=await route.fetch();const data=await response.json();data.meta.ai_configured=true;await route.fulfill({json:data})});
 let voiceFail=true;
 await page.route('**/api/realtime/session*',route=>route.fulfill(voiceFail?{status:502,json:{detail:'mock connection failure'}}:{body:'mock-answer',contentType:'application/sdp'}));
 await page.reload();
 await page.getByLabel('음성 시작',{exact:true}).click();
 await page.getByText('mock connection failure',{exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>window.__voice.stopped),1);
 voiceFail=false;
 await page.getByLabel('음성 시작',{exact:true}).click();
 await page.getByRole('button',{name:'음소거',exact:true}).waitFor();
 await page.getByRole('button',{name:'음소거',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.__voice.track.enabled),false);
 await page.getByRole('button',{name:'음소거 해제',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.__voice.track.enabled),true);
 await page.evaluate(()=>window.__voice.dc.onmessage({data:JSON.stringify({type:'input_audio_buffer.speech_started'})}));
 await page.getByText('음성 연결 · speaking',{exact:false}).waitFor();
 const voiceEvent=event=>page.evaluate(event=>window.__voice.dc.onmessage({data:JSON.stringify(event)}),event);
 const responseCount=()=>page.evaluate(()=>window.__voice.sent.filter(e=>e.type==='response.create').length);
 await voiceEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'ambient1',transcript:'오늘 재고 알려줘'});
 assert.equal(await responseCount(),0);
 assert.equal(await page.locator('.message.user').count(),0);
 await voiceEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'named1',transcript:'송월아, 오늘 재고 알려줘'});
 assert.equal(await responseCount(),1);
 assert.equal(await page.evaluate(()=>window.__voice.sent.filter(e=>e.type==='conversation.item.create').length),0);
 await voiceEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'named1',transcript:'송월아, 오늘 재고 알려줘'});
 assert.equal(await responseCount(),1); // Duplicate recognition cannot double the answer.
 await voiceEvent({type:'response.output_audio_transcript.done',transcript:'테스트 재고 답변'});
 await voiceEvent({type:'response.done'});
 await page.getByText('테스트 재고 답변',{exact:true}).waitFor();
 await voiceEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'ambient2',transcript:'내일도 알려줘'});
 assert.equal(await responseCount(),1); // Wake permission never carries over to the next question.
 await voiceEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'brand',transcript:'송월타월 재고 알려줘'});
 assert.equal(await responseCount(),1);
 let releaseTool;
 await page.route('**/api/realtime/tool',route=>new Promise(resolve=>{releaseTool=async()=>{await route.fulfill({json:{output:'{}',evidence:[]}});resolve()}}));
 await voiceEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'named2',transcript:'송월아 내일 출하 알려줘'});
 assert.equal(await responseCount(),2);
 await voiceEvent({type:'response.function_call_arguments.done',name:'get_daily_operations',call_id:'call-test',arguments:'{}'});
 await voiceEvent({type:'response.done'});
 await voiceEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'ambient3',transcript:'오늘 날씨가 좋네'});
 assert.equal(await responseCount(),2); // A pending data lookup must not unlock ambient speech.
 await page.waitForTimeout(50);
 await releaseTool();
 await page.waitForFunction(()=>window.__voice.sent.filter(e=>e.type==='response.create').length===3);
 await voiceEvent({type:'response.done'});
 await voiceEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'ambient4',transcript:'그리고 다음 주는'});
 assert.equal(await responseCount(),3);
 await page.unroute('**/api/realtime/tool');
 await page.getByRole('button',{name:'종료',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.__voice.stopped),2);
 await page.getByLabel('음성 시작',{exact:true}).click();
 await page.getByRole('button',{name:'음소거',exact:true}).waitFor();
 await page.getByLabel('조회 LOT').selectOption('PRT-260902-B');
 assert.equal(await page.evaluate(()=>window.__voice.stopped),3);
 await page.getByLabel('음성 시작',{exact:true}).click();
 await page.getByRole('button',{name:'음소거',exact:true}).waitFor();
 await menu.getByRole('link',{name:'현장',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.__voice.stopped),4);
 await menu.getByRole('link',{name:'대화',exact:true}).click();
 await page.evaluate(()=>window.__voice.deny=true);
 await page.getByLabel('음성 시작',{exact:true}).click();
 await page.getByText('마이크 권한을 허용해 주세요.',{exact:true}).waitFor();
 // API-key setup is mocked: no real key is written and no paid voice session starts.
 await page.unroute('**/api/workspace');
 let configured=false,saveFails=true;
 const fakeKey='sk-ui-test-'+ 'x'.repeat(40);
 await page.route('**/api/workspace',async route=>{const response=await route.fetch();const data=await response.json();data.meta.ai_configured=configured;data.meta.access_required=false;await route.fulfill({json:data})});
 await page.route('**/api/settings/openai',async route=>{
  assert.equal(route.request().postDataJSON().api_key===fakeKey,true);
  if(saveFails)return route.fulfill({status:422,json:{detail:'테스트 키 확인 실패'}});
  configured=true;await route.fulfill({json:{configured:true}});
 });
 await page.goto('http://127.0.0.1:8513/?setup=openai#/assistant');
 await page.getByLabel('OpenAI API 키',{exact:true}).waitFor();
 await page.screenshot({path:'artifacts/voice-setup-mobile.png',fullPage:true});
 await page.getByLabel('OpenAI API 키',{exact:true}).fill(fakeKey);
 await page.getByRole('button',{name:'저장하고 음성 시작',exact:true}).click();
 await page.getByText('테스트 키 확인 실패',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('OpenAI API 키',{exact:true}).inputValue(),'');
 saveFails=false;
 await page.getByLabel('OpenAI API 키',{exact:true}).fill(fakeKey);
 await page.getByRole('button',{name:'저장하고 음성 시작',exact:true}).click();
 await page.getByRole('button',{name:'음소거',exact:true}).waitFor();
 assert.equal(await page.locator('dialog[open]').count(),0);
 assert.equal(await page.evaluate(key=>JSON.stringify(localStorage).includes(key)||JSON.stringify(sessionStorage).includes(key),fakeKey),false);
 await page.getByRole('button',{name:'종료',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.__voice.stopped),1);
 assert.deepEqual(errors,[]);
 await browser.close();
 console.log('PASS: routes/operations/LOT context/back-forward/library/retry/mobile panels plus desktop/mobile documents, records, chat, evidence, history, reset, LOT race, overflow, console errors and mocked voice wake gating/duplicate suppression/tool continuation/failure/mute/stop/LOT cleanup/permission');
})().catch(e=>{console.error(e);process.exit(1)});
