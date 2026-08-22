// Is the header's backdrop-filter actually painting? Diff the same strip with it on and forced off.
import { chromium } from "playwright"; import { PNG } from "pngjs"; import { writeFileSync } from "node:fs";
const SITE="http://127.0.0.1:3100", OUT="/tmp/claude-0/-home-user-GozarX/c019534b-02b6-53f9-aaf3-f0202784f44e/scratchpad/out";
const b=await chromium.launch({executablePath:"/opt/pw-browsers/chromium-1194/chrome-linux/chrome"});
const ctx=await b.newContext({viewport:{width:390,height:780},deviceScaleFactor:2,isMobile:true,hasTouch:true,locale:"fa-IR",extraHTTPHeaders:{"accept-language":"fa-IR,fa;q=0.9"},colorScheme:"dark"});
await ctx.addCookies([{name:"theme",value:"dark",url:SITE},{name:"locale",value:"fa",url:SITE}]);
const p=await ctx.newPage(); await p.goto(`${SITE}/`,{waitUntil:"networkidle"}).catch(()=>{});
await p.evaluate(()=>document.fonts?.ready);
await p.addStyleTag({content:"*{animation:none!important;transition:none!important}"});
await p.evaluate(()=>scrollTo(0,1500)); await p.waitForTimeout(500);
const clip={x:0,y:0,width:390,height:63};
const on=PNG.sync.read(await p.screenshot({clip})); writeFileSync(`${OUT}/hd-on.png`, PNG.sync.write(on));
await p.addStyleTag({content:"header.hd{backdrop-filter:none!important;-webkit-backdrop-filter:none!important}"});
await p.waitForTimeout(300);
const off=PNG.sync.read(await p.screenshot({clip})); writeFileSync(`${OUT}/hd-off.png`, PNG.sync.write(off));
let diff=0,max=0;
for(let i=0;i<on.data.length;i+=4){const d=Math.abs(on.data[i]-off.data[i])+Math.abs(on.data[i+1]-off.data[i+1])+Math.abs(on.data[i+2]-off.data[i+2]); if(d>6)diff++; if(d>max)max=d;}
console.log(`pixels differing (>6/765): ${diff} of ${on.width*on.height} (${(diff/(on.width*on.height)*100).toFixed(1)}%)  maxDelta=${max}`);
console.log(diff>200 ? "=> backdrop-filter IS painting (blur is doing work)" : "=> backdrop-filter has NO visible effect here");
// opaque comparison: how much does the content behind show through?
await p.addStyleTag({content:"header.hd{background:#020617!important;backdrop-filter:none!important}"});
await p.waitForTimeout(300);
const solid=PNG.sync.read(await p.screenshot({clip}));
let d2=0,m2=0;
for(let i=0;i<on.data.length;i+=4){const d=Math.abs(on.data[i]-solid.data[i])+Math.abs(on.data[i+1]-solid.data[i+1])+Math.abs(on.data[i+2]-solid.data[i+2]); if(d>6)d2++; if(d>m2)m2=d;}
console.log(`vs a fully OPAQUE header: ${d2} px differ (${(d2/(on.width*on.height)*100).toFixed(1)}%), maxDelta=${m2}  <- this is the content bleeding through`);
writeFileSync(`${OUT}/hd-solid.png`, PNG.sync.write(solid));
await b.close();
