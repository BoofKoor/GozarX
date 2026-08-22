import { chromium } from "playwright";
const SITE="http://127.0.0.1:3100", OUT="/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const ctx=await b.newContext({viewport:{width:390,height:780},deviceScaleFactor:2,isMobile:true,hasTouch:true,
  locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
await p.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,40));}scrollTo(0,0);await new Promise(r=>setTimeout(r,200));});
await p.evaluate(()=>document.fonts?.ready);
await p.addStyleTag({content:"*{animation:none!important;transition:none!important}"});
await p.waitForTimeout(400);
for(const [name,sel,pad] of [["pr1-steps",".steps",8],["pr1-footer-keywords",".ft-more",8],
    ["pr1-trust-badges",".trust-badges",10],["pr1-flagstrip",".flagstrip",8],["pr1-header",".hd-row",6]]){
  const el=p.locator(sel).first(); if(!(await el.count())) {console.log("missing",name);continue;}
  await el.scrollIntoViewIfNeeded(); await p.waitForTimeout(150);
  const bx=await el.boundingBox(); if(!bx) continue;
  await p.screenshot({path:`${OUT}/${name}.png`,clip:{x:Math.max(0,bx.x-pad),y:Math.max(0,bx.y-pad),
    width:Math.min(390-Math.max(0,bx.x-pad),bx.width+pad*2),height:bx.height+pad*2}});
}
// header over content
await p.evaluate(()=>scrollTo(0,1200)); await p.waitForTimeout(300);
await p.screenshot({path:`${OUT}/pr1-header-scrolled.png`,clip:{x:0,y:0,width:390,height:140}});
await b.close(); console.log("crops written");
