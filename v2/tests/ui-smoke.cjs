// PLAYWRIGHT_MODULE can point to an existing local Playwright installation.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:960}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8513');
 await page.getByRole('button',{name:'원단·인쇄 LOT 추적 SOP'}).waitFor();
 await page.screenshot({path:'artifacts/desktop.png',fullPage:true});
 await page.getByLabel('문서 검색').fill('클레임');
 await page.getByRole('button',{name:'클레임 대응 매뉴얼'}).click();
 assert.match(await page.locator('dialog[open]').innerText(),/미승인/);
 await page.getByLabel('문서 닫기',{exact:true}).click();
 await page.getByRole('button',{name:'데이터허브',exact:true}).click();
 await page.getByLabel('조회 테이블').selectOption('lot_quality');
 await page.locator('summary').filter({hasText:'QI-260903'}).click();
 await page.getByText('4.7',{exact:true}).waitFor();
 await page.getByLabel('조회 LOT').selectOption('PRT-260903-C');
 await page.getByLabel('질문 입력').fill('품질과 출하 상태');
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
 await page.getByLabel('질문 입력').fill('늦은 응답 테스트');
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
 await page.getByRole('button',{name:'01 인쇄 품질 기준서를 찾아줘'}).click();
 await page.locator('.message.assistant').waitFor();
 await page.screenshot({path:'artifacts/mobile-answer.png',fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.deepEqual(errors,[]);

 // Mock media and the provider boundary: no microphone or paid AI call is used.
 await page.addInitScript(()=>{
  window.__voice={stopped:0,closed:0,deny:false};
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
   createDataChannel(){this.dc={readyState:'connecting',close(){},send(){}};window.__voice.dc=this.dc;return this.dc}
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
 await page.getByRole('button',{name:'종료',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.__voice.stopped),2);
 await page.getByLabel('음성 시작',{exact:true}).click();
 await page.getByRole('button',{name:'음소거',exact:true}).waitFor();
 await page.getByLabel('조회 LOT').selectOption('PRT-260902-B');
 assert.equal(await page.evaluate(()=>window.__voice.stopped),3);
 await page.evaluate(()=>window.__voice.deny=true);
 await page.getByLabel('음성 시작',{exact:true}).click();
 await page.getByText('마이크 권한을 허용해 주세요.',{exact:true}).waitFor();
 await browser.close();
 console.log('PASS: desktop/mobile documents, records, chat, evidence, history, reset, LOT race, overflow, console errors and mocked voice failure/mute/interruption/stop/LOT cleanup/permission');
})().catch(e=>{console.error(e);process.exit(1)});
