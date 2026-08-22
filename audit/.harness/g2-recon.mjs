// Both the doc-height gap (+87) and the CTA gap (+88.7) are the same size, so ONE element above the
// CTA must be taller in the measured build. The hero subtitle is admin-editable (app/page.tsx:59 →
// copy.hero_sub), so it is the only string on that path whose length is not fixed by the repo.
import { chromium } from "playwright";
const SITE="http://127.0.0.1:3100";
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const measure=async(extraLines)=>{
  const ctx=await b.newContext({viewport:{width:390,height:780},deviceScaleFactor:1,isMobile:true,hasTouch:true,
    locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
  await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
  const p=await ctx.newPage();
  await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
  await p.evaluate(()=>document.fonts?.ready);
  if(extraLines>0) await p.evaluate((n)=>{
    const s=document.querySelector(".hero-copy .sub");
    s.textContent = s.textContent + " " + "و یک جملهٔ اضافه برای رساندن زیرتیتر به طول بیشتر.".repeat(n);
  },extraLines);
  await p.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,30));}scrollTo(0,0);await new Promise(r=>setTimeout(r,150));});
  await p.waitForTimeout(250);
  const r=await p.evaluate(()=>{const c=document.querySelector(".cta").getBoundingClientRect();
    const s=document.querySelector(".hero-copy .sub").getBoundingClientRect();
    return {doc:document.documentElement.scrollHeight,ctaTop:Math.round(c.top+scrollY),
      ctaBottom:Math.round(c.bottom+scrollY),subH:Math.round(s.height),
      subLines:Math.round(s.height/parseFloat(getComputedStyle(document.querySelector(".hero-copy .sub")).lineHeight))};});
  await ctx.close(); return r;
};
console.log("hero .sub length  →  doc height / CTA top / CTA bottom / sub height / sub lines");
for(const n of [0,1,2,3]){
  const r=await measure(n);
  console.log(`  +${n} sentence(s): doc=${r.doc}  ctaTop=${r.ctaTop}  ctaBottom=${r.ctaBottom}  subH=${r.subH} (${r.subLines} lines)`);
}
console.log("\naddendum figures to match: doc=7995  ctaTop=964");
await b.close();
