import { chromium } from "playwright";
const SITE="http://127.0.0.1:3100";
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const ctx=await b.newContext({viewport:{width:390,height:780},deviceScaleFactor:2,isMobile:true,hasTouch:true,locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
const p=await ctx.newPage();
await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
await p.evaluate(()=>document.fonts?.ready); await p.waitForTimeout(600);
console.log(JSON.stringify(await p.evaluate(()=>{
  const s=document.querySelector(".loc-scroll"), g=document.querySelector(".loc-scroll > .loc-grid");
  const after=getComputedStyle(s,"::after");
  const hd=document.querySelector("header.hd");
  const cs=getComputedStyle(hd);
  return {
    locScroll:{ hasMoreClass:s.classList.contains("more"), classes:s.className,
      afterOpacity:after.opacity, afterBg:after.backgroundImage.slice(0,60), afterHeight:after.blockSize||after.height,
      gridMaxH:getComputedStyle(g).maxHeight, gridScrollH:g.scrollHeight, gridClientH:g.clientHeight,
      overscroll:getComputedStyle(g).overscrollBehavior, scrollbarWidth:getComputedStyle(g).scrollbarWidth,
      rowsVisible:+(g.clientHeight/((g.scrollHeight)/Math.ceil(29/3))).toFixed(2) },
    header:{ backdropFilter:cs.backdropFilter||cs.webkitBackdropFilter,
      bg:cs.backgroundColor, bgAlpha:(cs.backgroundColor.match(/\/\s*([\d.]+)\)/)||[])[1]||"1",
      supportsBackdrop: CSS.supports("backdrop-filter","blur(1px)"),
      isolation:cs.isolation, willChange:cs.willChange, contain:cs.contain },
    trustCard:{ textAlign:getComputedStyle(document.querySelector(".trust-card")).textAlign },
    // does an ancestor break backdrop-filter? (filter/transform/perspective on any ancestor)
    ancestorsWithFilter:(()=>{let out=[],e=hd.parentElement;
      while(e&&e!==document.documentElement){const c=getComputedStyle(e);
        if(c.filter!=="none"||c.transform!=="none"||c.perspective!=="none"||c.contain!=="none"||c.willChange!=="auto")
          out.push({el:e.tagName+"."+e.className,filter:c.filter,transform:c.transform,contain:c.contain,willChange:c.willChange});
        e=e.parentElement;} return out;})(),
  };
}),null,2));
await b.close();
