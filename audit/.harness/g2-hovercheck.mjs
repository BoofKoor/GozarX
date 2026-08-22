// The CSSOM walk returned 0 rules, which would make "unguarded == 0" pass vacuously. Verify the
// guard two ways that cannot both be wrong: parse the SERVED stylesheet text, and check the rule's
// actual effect under hover:none vs hover:hover.
import { chromium } from "playwright";
const SITE="http://127.0.0.1:3100";
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const ctx=await b.newContext({viewport:{width:390,height:780},deviceScaleFactor:1,isMobile:true,hasTouch:true,
  locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
const diag=await p.evaluate(async()=>{
  const sheets=[...document.styleSheets].map(s=>{
    let n=null,err=null; try{n=s.cssRules.length}catch(e){err=String(e.name)}
    return {href:s.href?s.href.split("/").pop():"(inline)",rules:n,err};});
  // fetch the stylesheet TEXT and parse it — immune to CSSOM quirks
  const link=[...document.querySelectorAll('link[rel=stylesheet]')].map(l=>l.href);
  const texts=await Promise.all(link.map(u=>fetch(u).then(r=>r.text())));
  const css=texts.join("\n");
  // strip guarded blocks, then look for what is left
  let stripped=css, guarded=0;
  const re=/@media\s*\(hover:\s*hover\)\s*\{/g;
  let m;
  while((m=re.exec(stripped))!==null){
    let i=m.index+m[0].length, depth=1;
    while(i<stripped.length&&depth>0){ if(stripped[i]==="{")depth++; else if(stripped[i]==="}")depth--; i++; }
    guarded++;
    stripped=stripped.slice(0,m.index)+stripped.slice(i);
    re.lastIndex=m.index;
  }
  const leftover=(stripped.match(/:hover/g)||[]).length;
  const leftoverSelectors=[...stripped.matchAll(/([^{}@]*:hover[^{}]*)\{/g)].map(x=>x[1].trim().slice(0,60)).slice(0,20);
  return { sheets, totalHoverInCss:(css.match(/:hover/g)||[]).length, guardedBlocks:guarded,
           hoverOutsideAGuard:leftover, leftoverSelectors,
           matchesHoverHover: matchMedia("(hover: hover)").matches,
           matchesHoverNone: matchMedia("(hover: none)").matches };
});
console.log(JSON.stringify(diag,null,2));
// behavioural: the appcard hover border must NOT apply on a touch context
const beh=await p.evaluate(()=>{
  const c=document.querySelector(".appcard");
  return { borderNow:getComputedStyle(c).borderTopColor };
});
console.log("appcard border (touch ctx, no hover applied):",beh.borderNow);
await ctx.close();
const ctx2=await b.newContext({viewport:{width:1280,height:900},deviceScaleFactor:1,isMobile:false,hasTouch:false,colorScheme:"dark"});
const p2=await ctx2.newPage(); await p2.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
console.log("desktop ctx matches (hover:hover):",await p2.evaluate(()=>matchMedia("(hover: hover)").matches));
await p2.locator(".appcard").first().hover();
await p2.waitForTimeout(300);
console.log("appcard border while hovered on DESKTOP:",await p2.evaluate(()=>getComputedStyle(document.querySelector(".appcard")).borderTopColor));
await b.close();
