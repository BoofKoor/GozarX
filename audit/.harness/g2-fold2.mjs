import { chromium } from "playwright"; import { writeFile } from "node:fs/promises";
const SITE="http://127.0.0.1:3100", OUT="/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const FOLD=718, MARGIN=16, TARGET=FOLD-MARGIN, WIDTHS=[360,390,393,412];
const CHROME = `
  #app .hero{ padding-block:12px 44px !important }
  #app .hero-copy h1{ margin:0 0 10px !important }
  #app .hero-copy .sub{ margin-block-end:14px !important }
  #app #hero-widget .widget{ padding:18px !important }
  #app .w-head{ margin-block-end:12px !important }
  #app .cta-wrap{ margin-block-start:14px !important }`;
const COMBOS = {
  "1 · chrome only (7 changes, keeps everything)": CHROME + `
  #app .loc-scroll > .loc-grid{ max-block-size:196px !important }`,
  "2 · chrome + picker to one row + peek": CHROME + `
  #app .loc-scroll > .loc-grid{ max-block-size:160px !important }`,
  "3 · #2 + hero sub 17→15.5px": CHROME + `
  #app .loc-scroll > .loc-grid{ max-block-size:160px !important }
  #app .hero-copy .sub{ font-size:15.5px !important }`,
  "4 · #3 + trust row moved below the widget": CHROME + `
  #app .loc-scroll > .loc-grid{ max-block-size:160px !important }
  #app .hero-copy .sub{ font-size:15.5px !important }
  @media (max-width:939px){ #app .hero-inner{ display:flex; flex-direction:column }
    #app .hero-copy{ display:contents }
    #app .hero-copy h1{ order:1 } #app .hero-copy .sub{ order:2 }
    #app #hero-widget{ order:3 } #app .trust-row{ order:4; margin-block-start:14px } }`,
  "5 · #3 + trust row hidden on mobile": CHROME + `
  #app .loc-scroll > .loc-grid{ max-block-size:160px !important }
  #app .hero-copy .sub{ font-size:15.5px !important }
  @media (max-width:939px){ #app .trust-row{ display:none !important } }`,
};
const read=()=>{const px=v=>Math.round(v*10)/10;const c=document.querySelector(".cta").getBoundingClientRect();
  const t=document.querySelector(".trust-row"); const tr=t?t.getBoundingClientRect():null;
  return{top:px(c.top+scrollY),bottom:px(c.bottom+scrollY),doc:px(document.documentElement.scrollHeight),
    trustTop:tr?px(tr.top+scrollY):null, trustVisible: tr? tr.height>0:false};};
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const measure=async(w,css)=>{const ctx=await b.newContext({viewport:{width:w,height:780},deviceScaleFactor:1,isMobile:true,hasTouch:true,
  locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
  await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
  const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
  await p.evaluate(()=>document.fonts?.ready); if(css) await p.addStyleTag({content:css});
  await p.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,30));}scrollTo(0,0);await new Promise(r=>setTimeout(r,150));});
  await p.waitForTimeout(250); const r=await p.evaluate(read); await ctx.close(); return r;};
const out={};
out.baseline={}; for(const w of WIDTHS) out.baseline[w]=await measure(w,"");
for(const [n,css] of Object.entries(COMBOS)){out[n]={}; for(const w of WIDTHS) out[n][w]=await measure(w,css);}
// screenshot the winner at 390 with the fold drawn in
const winner=Object.keys(COMBOS).find(n=>out[n][390].bottom<=TARGET) || Object.keys(COMBOS).slice(-1)[0];
{const ctx=await b.newContext({viewport:{width:390,height:FOLD},deviceScaleFactor:2,isMobile:true,hasTouch:true,
  locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
 await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
 const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
 await p.evaluate(()=>document.fonts?.ready); await p.addStyleTag({content:COMBOS[winner]});
 await p.waitForTimeout(500); await p.screenshot({path:`${OUT}/fold-after.png`});
 await ctx.close();}
{const ctx=await b.newContext({viewport:{width:390,height:FOLD},deviceScaleFactor:2,isMobile:true,hasTouch:true,
  locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
 await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
 const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
 await p.evaluate(()=>document.fonts?.ready); await p.waitForTimeout(500);
 await p.screenshot({path:`${OUT}/fold-before.png`}); await ctx.close();}
await b.close(); await writeFile(`${OUT}/g2-fold2.json`,JSON.stringify(out,null,2));
console.log(`target: CTA bottom <= ${TARGET} (fold ${FOLD} - ${MARGIN} margin)\n`);
console.log("combination".padEnd(46)+WIDTHS.map(w=>String(w).padStart(9)).join("")+"   trust row");
for(const n of ["baseline",...Object.keys(COMBOS)]){
  const cells=WIDTHS.map(w=>{const v=out[n][w].bottom;return `${v}${v<=TARGET?"*":" "}`.padStart(9);}).join("");
  console.log(n.padEnd(46)+cells+`   ${out[n][390].trustVisible?"visible y="+out[n][390].trustTop:"HIDDEN"}`);
}
console.log("\n* = CTA bottom is above the fold line with a 16px margin");
console.log("\ndoc height for each: "+["baseline",...Object.keys(COMBOS)].map(n=>`${n.split(" ")[0]}=${out[n][390].doc}`).join("  "));
console.log("winner screenshotted:", winner);
