// Gate 2 · item 3 — the BUILT PR-1 branch, measured. No per-rule deltas are summed anywhere here;
// this reads scrollHeight off the running build under the Gate-1 conditions.
import { chromium } from "playwright"; import { writeFile } from "node:fs/promises";
const SITE="http://127.0.0.1:3100", OUT="/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const WIDTHS=[360,390,393,412];
const probe=()=>{
  const px=v=>Math.round(v*10)/10;
  const cta=document.querySelector(".cta");
  const c=cta?cta.getBoundingClientRect():null;
  const secs=[...document.querySelectorAll("main section")];
  const chip=document.querySelector(".art-chips .chip");
  const ftm=[...document.querySelectorAll(".ft-more a")];
  const burger=document.querySelector(".burger"), acct=document.querySelector(".acct-btn");
  const anti=document.querySelector(".antibot");
  const step=document.querySelector(".step"), num=document.querySelector(".step .num"), h3=document.querySelector(".step h3");
  const fs=[...document.querySelectorAll(".flagstrip > *")].map(e=>Math.round(e.getBoundingClientRect().top));
  const tb=[...document.querySelectorAll(".trust-badges > *")].map(e=>Math.round(e.getBoundingClientRect().top));
  // The CSSOM walk reported 0 rules on the built CSS (CSSRule.type is deprecated and no longer
  // identifies a media rule reliably), which would make "unguarded == 0" pass VACUOUSLY. Parse the
  // served stylesheet text instead: strip every @media (hover:hover){...} block by brace-matching,
  // then anything with :hover still standing is unguarded.
  return {
    doc:px(document.documentElement.scrollHeight),
    ctaTop:c?px(c.top+scrollY):null, ctaBottom:c?px(c.bottom+scrollY):null, ctaH:c?px(c.height):null,
    sections:secs.length,
    sectionPadding:secs.length?getComputedStyle(secs[1]).paddingTop:null,
    homepageArtChips: document.querySelectorAll(".art-chips .chip").length,
    footerKeywordLinks: ftm.length,
    footerLinkHeight: ftm.length?px(ftm[0].getBoundingClientRect().height):null,
    footerSeparator: ftm.length>1?getComputedStyle(ftm[1],"::before").content:null,
    footerHeadingOwnLine: (()=>{const h=document.querySelector(".ft-more-h");
      return h&&ftm.length?Math.round(h.getBoundingClientRect().top)!==Math.round(ftm[0].getBoundingClientRect().top):null})(),
    burger:burger?[px(burger.getBoundingClientRect().width),px(burger.getBoundingClientRect().height)]:null,
    acct:acct?[px(acct.getBoundingClientRect().width),px(acct.getBoundingClientRect().height)]:null,
    antibotColor:anti?getComputedStyle(anti).color:null,
    headerBg:getComputedStyle(document.querySelector("header.hd")).backgroundColor,
    stepIconSharesRowWithTitle: (num&&h3)?Math.abs(num.getBoundingClientRect().top-h3.getBoundingClientRect().top)<24:null,
    stepHeight: step?px(step.getBoundingClientRect().height):null,
    flagstripLines:[...new Set(fs)].length, flagstripPerLine:(()=>{const u=[...new Set(fs)].sort((a,b)=>a-b);return u.map(t=>fs.filter(x=>x===t).length)})(),
    trustBadgeLines:[...new Set(tb)].length, trustBadgePerLine:(()=>{const u=[...new Set(tb)].sort((a,b)=>a-b);return u.map(t=>tb.filter(x=>x===t).length)})(),
    secSubTextWrap:getComputedStyle(document.querySelector(".sec-sub")).textWrap,
    horizontalOverflow: document.documentElement.scrollWidth>window.innerWidth,
  };
};
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const out={};
for(const w of WIDTHS){
  const ctx=await b.newContext({viewport:{width:w,height:780},deviceScaleFactor:2,isMobile:true,hasTouch:true,
    locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
  await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
  const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle",timeout:45000}).catch(()=>{});
  await p.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,40));}scrollTo(0,0);await new Promise(r=>setTimeout(r,200));});
  await p.evaluate(()=>document.fonts?.ready); await p.waitForTimeout(350);
  out[w]=await p.evaluate(probe);
  out[w].hoverRules=await p.evaluate(async()=>{
    const hrefs=[...document.querySelectorAll('link[rel=stylesheet]')].map(l=>l.href);
    const css=(await Promise.all(hrefs.map(u=>fetch(u).then(r=>r.text())))).join("\n");
    const total=(css.match(/:hover/g)||[]).length;
    let stripped=css,guarded=0; const re=/@media\s*\(hover:\s*hover\)\s*\{/g; let m;
    while((m=re.exec(stripped))!==null){ let i=m.index+m[0].length,d=1;
      while(i<stripped.length&&d>0){ if(stripped[i]==="{")d++; else if(stripped[i]==="}")d--; i++; }
      guarded++; stripped=stripped.slice(0,m.index)+stripped.slice(i); re.lastIndex=m.index; }
    return {total,guardedBlocks:guarded,unguarded:(stripped.match(/:hover/g)||[]).length};});
  await p.screenshot({path:`${OUT}/pr1-${w}-full.png`,fullPage:true});
  await ctx.close();
}
await b.close(); await writeFile(`${OUT}/g2-pr1.json`,JSON.stringify(out,null,2));
const BASE={360:8049,390:7908,393:7881,412:7786};
console.log("=== PR 1, BUILT AND MEASURED (mobile emulation, Accept-Language: fa-IR, full scroll) ===\n");
console.log("width   Gate-1 baseline   PR 1 measured        Δ      CTA bottom   h-overflow");
for(const w of WIDTHS){const o=out[w];
  console.log(`${String(w).padStart(5)}   ${String(BASE[w]).padStart(15)}   ${String(o.doc).padStart(13)}   ${String(Math.round((o.doc-BASE[w])*10)/10).padStart(6)}   ${String(o.ctaBottom).padStart(10)}   ${o.horizontalOverflow}`);}
const o=out[390];
console.log("\n=== the checks that must be non-vacuous (each fails on the Gate-1 build) ===");
console.log(`  .sec padding-block ....................... ${o.sectionPadding}          (was 56px)`);
console.log(`  .sec-sub text-wrap ....................... ${o.secSubTextWrap}       (was wrap)`);
console.log(`  homepage .art-chips .chip count .......... ${o.homepageArtChips}             (was 13)`);
console.log(`  footer keyword links ..................... ${o.footerKeywordLinks}            (was 13, unchanged)`);
console.log(`  footer keyword link height ............... ${o.footerLinkHeight}px         (was 22px)`);
console.log(`  footer link separator (::before content) . ${o.footerSeparator}          (was none)`);
console.log(`  footer heading on its own line ........... ${o.footerHeadingOwnLine}          (was false at >=390)`);
console.log(`  burger / account size .................... ${o.burger} / ${o.acct}  (was 38x38 / 38x38)`);
console.log(`  .antibot colour .......................... ${o.antibotColor}   (was rgb(100,116,139))`);
console.log(`  header background ........................ ${o.headerBg}`);
console.log(`  step icon shares a row with the title .... ${o.stepIconSharesRowWithTitle}          (was false)`);
console.log(`  step card height ......................... ${o.stepHeight}px        (was 194px)`);
console.log(`  flagstrip lines / per line ............... ${o.flagstripLines} / ${JSON.stringify(o.flagstripPerLine)}     (was 2 / [5,1])`);
console.log(`  trust-badges lines / per line ............ ${o.trustBadgeLines} / ${JSON.stringify(o.trustBadgePerLine)}  (was 2 / [2,1])`);
console.log(`  :hover in served CSS / guard blocks / UNGUARDED  ${o.hoverRules.total} / ${o.hoverRules.guardedBlocks} / ${o.hoverRules.unguarded}   (Gate-1 build: 94 / 0 / 94)`);
