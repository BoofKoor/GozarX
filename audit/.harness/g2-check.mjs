import { chromium } from "playwright";
const SITE="http://127.0.0.1:3100";
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const ctx=await b.newContext({viewport:{width:390,height:780},deviceScaleFactor:1,isMobile:true,hasTouch:true,
  locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
await p.evaluate(()=>document.fonts?.ready); await p.waitForTimeout(400);
console.log(JSON.stringify(await p.evaluate(()=>{
  const px=v=>Math.round(v*10)/10;
  const hd=document.querySelector("header.hd").getBoundingClientRect();
  const tbs=[...document.querySelectorAll(".trust-badges > *")];
  const cont=document.querySelector(".trust-badges").getBoundingClientRect();
  const gap=parseFloat(getComputedStyle(document.querySelector(".trust-badges")).columnGap)||0;
  const hero=document.querySelector(".hero").getBoundingClientRect();
  return {headerHeight:px(hd.height),
    trustBadgeWidths:tbs.map(e=>px(e.getBoundingClientRect().width)),
    trustBadgeNatural:px(tbs.reduce((s,e)=>s+e.getBoundingClientRect().width,0)+(tbs.length-1)*gap),
    trustContainerWidth:px(cont.width), gap,
    heroTop:px(hero.top+scrollY)};}),null,2));
await b.close();
