// The owner's ranking claims items 2–6 take the page from ~9,500px to ~7,500px. Rather than agree
// or disagree, apply each change in the live page and read the new document height.
import { chromium } from "playwright"; import { writeFileSync } from "node:fs";
const SITE="http://127.0.0.1:3100";
const CASES = {
  "baseline": "",
  "A1  .sec padding-block 56→32": "#app .sec{padding-block:32px !important}",
  "A1  .sec padding-block 56→28 + sec-head mb 40→24": "#app .sec{padding-block:28px !important} #app .sec-head{margin-bottom:24px !important}",
  "H1  drop the footer keyword row": "#app .ft-more{display:none !important}",
  "H1' drop the homepage article band instead": "#app #articles{display:none !important}",
  "D6  step icon inline with the title": "#app .step{display:grid;grid-template-columns:auto 1fr;grid-template-areas:'i t' '. b';column-gap:14px;align-items:center} #app .step .num{grid-area:i;margin-bottom:0 !important} #app .step h3{grid-area:t;margin:0 !important} #app .step p{grid-area:b;margin-top:8px !important}",
  "B2  picker 268→196px (1.5 rows)": "#app .loc-scroll > .loc-grid{max-block-size:196px !important}",
  "hero widget min-height 610→520": "#hero-widget .widget{min-block-size:520px !important}",
  "ALL of the above together": null,
};
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const results={};
for (const width of [360,390,412]) {
  results[width]={};
  for (const [name,css] of Object.entries(CASES)) {
    const ctx=await b.newContext({viewport:{width,height:780},deviceScaleFactor:1,isMobile:true,hasTouch:true,locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
    await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
    const p=await ctx.newPage();
    await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
    await p.evaluate(()=>document.fonts?.ready);
    const sheet = css===null ? Object.values(CASES).filter(Boolean).join("\n") : css;
    if (sheet) await p.addStyleTag({content:sheet});
    await p.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,30));}scrollTo(0,0);await new Promise(r=>setTimeout(r,150));});
    await p.waitForTimeout(250);
    const h=await p.evaluate(()=>document.documentElement.scrollHeight);
    const ctaY=await p.evaluate(()=>{const c=document.querySelector(".cta");return c?Math.round(c.getBoundingClientRect().top+scrollY):null;});
    results[width][name]={height:h,ctaTop:ctaY};
    await ctx.close();
  }
}
console.log("case".padEnd(50)+["360","390","412"].map(w=>w.padStart(14)).join("")+"   CTA top @390");
const base={}; for(const w of [360,390,412]) base[w]=results[w]["baseline"].height;
for (const name of Object.keys(CASES)) {
  const cells=[360,390,412].map(w=>{const h=results[w][name].height;const d=h-base[w];return `${h} (${d>=0?"+":""}${d})`.padStart(14);}).join("");
  console.log(name.padEnd(50)+cells+`   ${results[390][name].ctaTop}`);
}
writeFileSync("/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out/savings.json",JSON.stringify(results,null,2));
await b.close();
