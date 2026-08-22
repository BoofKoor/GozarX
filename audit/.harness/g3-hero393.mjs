// A, B, C rendered at 393 in both themes, full hero block (not a tight crop), with treatment C's
// per-theme underline correction applied: the rule must clear WCAG 1.4.11 (3:1, non-text).
//   dark  #22D3EE on #05132f -> 10.19:1     light #0E7490 on #cfe5f7 -> 4.13:1
// (the uncorrected draft used --hero-2, which is #06B6D4 in light and measured 1.87:1)
import { chromium } from "playwright"; import { PNG } from "pngjs"; import { writeFile } from "node:fs/promises";
const SITE="http://127.0.0.1:3100", OUT="/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const lin=c=>{c/=255;return c<=0.04045?c/12.92:Math.pow((c+0.055)/1.055,2.4)};
const L=([r,g,b])=>0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b);
const ratio=(a,b)=>{const l1=L(a),l2=L(b),[h,lo]=l1>l2?[l1,l2]:[l2,l1];return Math.round(((h+0.05)/(lo+0.05))*100)/100};
const hex=([r,g,b])=>"#"+[r,g,b].map(v=>Math.round(v).toString(16).padStart(2,"0")).join("");
const T={
 A:`.hero-copy h1 .grad{ background:none!important; -webkit-background-clip:border-box!important;
     background-clip:border-box!important; color:var(--brand-tint-ink)!important;
     -webkit-text-fill-color:var(--brand-tint-ink)!important; }`,
 B:`#app[data-theme="dark"],#app:not([data-theme="light"]){--hero-grad-1:#3B82F6;--hero-grad-2:#22D3EE}
    #app[data-theme="light"]{--hero-grad-1:#1D4ED8;--hero-grad-2:#0E7490}
    .hero-copy h1 .grad{ background:linear-gradient(120deg,var(--hero-grad-1),var(--hero-grad-2))!important;
     -webkit-background-clip:text!important; background-clip:text!important;
     color:transparent!important; -webkit-text-fill-color:transparent!important; }
    [dir="rtl"] .hero-copy h1 .grad{ background:linear-gradient(240deg,var(--hero-grad-1),var(--hero-grad-2))!important;
     -webkit-background-clip:text!important; background-clip:text!important; }`,
 C:`#app[data-theme="dark"],#app:not([data-theme="light"]){--hero-rule:#22D3EE}
    #app[data-theme="light"]{--hero-rule:#0E7490}
    .hero-copy h1 .grad{ background:linear-gradient(var(--hero-rule),var(--hero-rule)) no-repeat!important;
     background-size:100% 3px!important; background-position:0 92%!important;
     -webkit-background-clip:border-box!important; background-clip:border-box!important;
     color:var(--text)!important; -webkit-text-fill-color:var(--text)!important;
     font-weight:900!important; font-size:1.14em!important; padding-block-end:.10em!important; }`,
};
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const res={};
for(const [k,css] of Object.entries(T)){
 res[k]={};
 for(const theme of ["dark","light"]){
  const ctx=await b.newContext({viewport:{width:393,height:820},deviceScaleFactor:2,isMobile:true,hasTouch:true,
   locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:theme});
  await ctx.addCookies([{name:"theme",value:theme,url:SITE},{name:"locale",value:"fa",url:SITE}]);
  const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
  await p.evaluate(()=>document.fonts?.ready);
  await p.addStyleTag({content:"*{animation:none!important;transition:none!important}"});
  await p.addStyleTag({content:css}); await p.waitForTimeout(500);
  // full hero block: from the top of the page down past the subtitle
  const box=await p.evaluate(()=>{const s=document.querySelector(".hero-copy .sub").getBoundingClientRect();
    return {h:Math.ceil(s.bottom+18)};});
  await p.screenshot({path:`${OUT}/g3-hero-${k}-${theme}-393.png`,clip:{x:0,y:0,width:393,height:box.h}});
  // and the rule's own contrast, measured from pixels, for C
  if(k==="C"){
   const r=await p.evaluate(()=>{const g=document.querySelector(".hero-copy h1 .grad").getBoundingClientRect();
     return {x:Math.round(g.left),y:Math.round(g.top),w:Math.round(g.width),h:Math.round(g.height)};});
   const png=PNG.sync.read(await p.screenshot({clip:{x:r.x,y:r.y+Math.round(r.h*0.86),width:r.w,height:Math.max(4,Math.round(r.h*0.14))}}));
   const counts=new Map();
   for(let i=0;i<png.data.length;i+=4){const key=`${png.data[i]},${png.data[i+1]},${png.data[i+2]}`;counts.set(key,(counts.get(key)||0)+1);}
   const sorted=[...counts.entries()].sort((a,c)=>c[1]-a[1]).slice(0,2).map(e=>e[0].split(",").map(Number));
   res[k][theme]={ruleColor:hex(sorted[0]),groundColor:hex(sorted[1]||sorted[0]),
     ruleRatio:ratio(sorted[0],sorted[1]||sorted[0])};
  } else res[k][theme]={};
  await ctx.close();
 }
}
await b.close(); await writeFile(`${OUT}/g3-hero393.json`,JSON.stringify(res,null,2));
console.log("treatment C, underline rule measured from pixels (WCAG 1.4.11 needs 3:1):");
for(const t of ["dark","light"]){const r=res.C[t];
 console.log(`  ${t.padEnd(5)} rule ${r.ruleColor} on ${r.groundColor} -> ${r.ruleRatio}:1  ${r.ruleRatio>=3?"PASS":"**FAIL**"}`);}
console.log("\nrendered: g3-hero-{A,B,C}-{dark,light}-393.png");
