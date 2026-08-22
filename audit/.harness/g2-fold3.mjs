import { chromium } from "playwright";
const SITE="http://127.0.0.1:3100", OUT="/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const FOLD=718,TARGET=702,WIDTHS=[360,390,393,412];
const CHROME=`#app .hero{padding-block:12px 44px!important} #app .hero-copy h1{margin:0 0 10px!important}
 #app .hero-copy .sub{margin-block-end:14px!important} #app #hero-widget .widget{padding:18px!important}
 #app .w-head{margin-block-end:12px!important} #app .cta-wrap{margin-block-start:14px!important}
 #app .loc-scroll > .loc-grid{max-block-size:196px!important}`;
const OPTS={
 "6 · chrome + widget FIRST on mobile (h1 below it)":CHROME+`
  @media (max-width:939px){ #app .hero-inner{display:flex;flex-direction:column}
   #app #hero-widget{order:1} #app .hero-copy{order:2;margin-block-start:22px} }`,
 "7 · #6 with the picker at one row + peek":CHROME+`
  #app .loc-scroll > .loc-grid{max-block-size:160px!important}
  @media (max-width:939px){ #app .hero-inner{display:flex;flex-direction:column}
   #app #hero-widget{order:1} #app .hero-copy{order:2;margin-block-start:22px} }`,
};
const read=()=>{const px=v=>Math.round(v*10)/10;const c=document.querySelector(".cta").getBoundingClientRect();
 const h=document.querySelector(".hero-copy h1").getBoundingClientRect();
 return{ctaBottom:px(c.bottom+scrollY),h1Top:px(h.top+scrollY),doc:px(document.documentElement.scrollHeight)};};
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const m=async(w,css)=>{const ctx=await b.newContext({viewport:{width:w,height:780},deviceScaleFactor:1,isMobile:true,hasTouch:true,
 locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
 await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
 const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
 await p.evaluate(()=>document.fonts?.ready); if(css)await p.addStyleTag({content:css});
 await p.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,30));}scrollTo(0,0);await new Promise(r=>setTimeout(r,150));});
 await p.waitForTimeout(250); const r=await p.evaluate(read); await ctx.close(); return r;};
console.log("option".padEnd(52)+WIDTHS.map(w=>String(w).padStart(9)).join("")+"    h1 top @390   doc @390");
for(const [n,css] of Object.entries(OPTS)){
 const res={}; for(const w of WIDTHS) res[w]=await m(w,css);
 console.log(n.padEnd(52)+WIDTHS.map(w=>`${res[w].ctaBottom}${res[w].ctaBottom<=TARGET?"*":" "}`.padStart(9)).join("")+`    ${String(res[390].h1Top).padStart(10)}   ${res[390].doc}`);
}
await b.close();
