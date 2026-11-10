const assert = require('node:assert/strict');

// Isolated browser contexts and synthetic codes: no real credential is persisted to disk.
module.exports = async function testAccessCode(browser) {
 const origin='http://127.0.0.1:8513';
 const code='test-remembered-code';
 const workspace={summary:{},lots:[],tables:{orders:'수주'},questions:{'생산·품질':[],'문서·규칙':[]},meta:{ai_configured:false,as_of:'2026-09-03',retrieved_at:'2026-10-09T00:00:00Z'}};
 async function context(options={}){
  const ctx=await browser.newContext(options);
  await ctx.route('**/api/**',route=>{
   const authorized=route.request().headers().authorization==='Bearer '+code;
   return route.fulfill(authorized?{json:route.request().url().endsWith('/workspace')?workspace:[]}:{status:401,json:{detail:'접근 코드를 확인해 주세요.'}});
  });
  return ctx;
 }
 let ctx=await context();
 let page=await ctx.newPage();page.setDefaultTimeout(10000);
 await page.goto(origin);
 await page.getByRole('dialog',{name:'연결 설정'}).waitFor();
 await page.getByLabel('접근 코드',{exact:true}).fill('incorrect-test-code');
 await page.getByRole('button',{name:'설정 저장',exact:true}).click();
 await page.getByRole('dialog',{name:'연결 설정'}).waitFor();
 assert.equal(await page.evaluate(()=>localStorage.getItem('songwol-token')===null),true);
 await page.getByLabel('접근 코드',{exact:true}).fill(code);
 await page.getByRole('button',{name:'설정 저장',exact:true}).click();
 await page.getByRole('heading',{name:'송월아',exact:true}).waitFor();
 assert.equal(await page.evaluate(value=>JSON.parse(localStorage.getItem('songwol-token'))===value,code),true);
 assert.equal(await page.evaluate(()=>sessionStorage.getItem('songwol-token')===null),true);
 // A new tab must reuse localStorage without a sessionStorage seed.
 const tab=await ctx.newPage();
 await tab.goto(origin);
 await tab.getByRole('heading',{name:'송월아',exact:true}).waitFor();
 assert.equal(await tab.locator('dialog[open]').count(),0);
 const state=await ctx.storageState();
 await ctx.close();
 // Restore only persistent browser state, as when restarting the browser.
 ctx=await context({storageState:state});page=await ctx.newPage();
 await page.goto(origin);
 await page.getByRole('heading',{name:'송월아',exact:true}).waitFor();
 assert.equal(await page.locator('dialog[open]').count(),0);
 await page.reload();
 await page.getByRole('heading',{name:'송월아',exact:true}).waitFor();
 assert.equal(await page.locator('dialog[open]').count(),0);
 await page.getByRole('button',{name:'설정',exact:true}).click();
 await page.getByRole('button',{name:'저장된 코드 지우기',exact:true}).click();
 await page.getByRole('dialog',{name:'연결 설정'}).waitFor();
 assert.equal(await page.evaluate(()=>localStorage.getItem('songwol-token')===null&&sessionStorage.getItem('songwol-token')===null),true);
 assert.equal(await page.getByLabel('접근 코드',{exact:true}).inputValue(),'');
 await ctx.close();
 // Migrate a previously signed-in tab without prompting for its code again.
 ctx=await context();page=await ctx.newPage();
 await page.addInitScript(value=>sessionStorage.setItem('songwol-token',JSON.stringify(value)),code);
 await page.goto(origin);
 await page.getByRole('heading',{name:'송월아',exact:true}).waitFor();
 assert.equal(await page.evaluate(value=>JSON.parse(localStorage.getItem('songwol-token'))===value,code),true);
 assert.equal(await page.locator('dialog[open]').count(),0);
 await ctx.close();
 console.log('PASS: one-time access code entry, rejection of invalid code, new tab, persistent browser state, reload, explicit removal and legacy migration');
};
