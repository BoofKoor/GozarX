# بررسی امکان‌سنجی: تله‌متری اتصال per-ASN از نودهای Remnawave

> **وضعیت: گزارش بررسی — هیچ کدی نوشته نشده.** خروجی این سند یک تصمیم معماری است، نه یک پیاده‌سازی.
> تا تأیید معماری، هیچ فایلی در `backend/` یا `frontend/` لمس نمی‌شود.

---

## ۰. خلاصه‌ی اجرایی

| سؤال | جواب کوتاه |
|---|---|
| Remnawave این داده را دارد؟ | **نه.** هیچ‌کدام از پنج فیلد خواسته‌شده وجود ندارد. آنچه هست: ترافیک ساعتی per-node و ترافیک روزانه per-(user,node). |
| کانال پنل↔نود؟ | **HTTPS REST + mTLS (TLSv1.3) + JWT، فقط pull.** نود آدرس پنل را اصلاً نمی‌داند و **نمی‌تواند push کند**. |
| Xray چه می‌دهد؟ | شمارنده‌های **تجمعی** (per-user، per-inbound)، لیست IPهای آنلاین per-user، و — کشف اصلی — **یک webhook در سطح قاعده‌ی مسیریابی** که per-connection متادیتا (شامل IP مبدأ) می‌فرستد. **بایت و مدت در آن نیست.** |
| ASN از کجا؟ | نود **از قبل** یک پایگاه ASN دارد (`/usr/local/share/asn/asn-prefixes.lmdb`) — ولی جهتش برعکس است (ASN→prefix). معکوس‌کردنش اندازه‌گیری شد: **۵ MB، زیر ۱ µs**. |
| نرخ شکست DPI؟ | **قابل اندازه‌گیری نیست و هیچ جایگزینی هم آن را نمی‌دهد.** سه سیگنال جایگزین هست که هرکدام چیز *دیگری* می‌گویند — بخش ۵ صریح می‌گوید هرکدام چه می‌تواند و چه نمی‌تواند. |
| توسعه‌پذیری؟ | «plugin» نود یک مجموعه‌ی **ثابت پنج‌تایی** است، بارگذارِ کد نیست. **اما** به احتمال زیاد fork لازم نیست: webhook خودِ Xray یک URL دلخواه می‌گیرد و پنل قواعد مسیریابی را اعتبارسنجی نمی‌کند. |
| سربار؟ | با dedup فعال ناچیز؛ **بدون dedup معنادار** (ده‌ها هزار POST در دقیقه). عدد در بخش ۷. |

**توصیه: معماری «الف» — سرویس تجمیع کنار نود (sidecar)، تغذیه‌شده از webhook خودِ Xray، بدون fork.** دلیل کامل در بخش ۹.

**بزرگ‌ترین ریسکِ نامعلوم — و باید همین حالا جواب داده شود:** آیا ما به *خودِ ماشین نود* دسترسی shell داریم؟ کل بحث با فرض «بله» نوشته شده. اگر نودها را شخص دیگری می‌گرداند و ما فقط یک API token پنل داریم، **هر سه معماری غیرممکن است** و تنها چیزی که می‌ماند بخش ۵.۵ است (مخرج از سمت خودمان).

---

## ۱. روش بررسی

هیچ چیزی از حافظه نقل نشده. هر ادعا از کدی است که در همین بررسی خوانده یا اجرا شده:

| منبع | نسخه | commit | تاریخ |
|---|---|---|---|
| `remnawave/node` | 3.0.0 | `46fc5d2` | 2026-08-02 |
| `remnawave/backend` | 3.2.1 | `1a80d12` | 2026-08-04 |
| `XTLS/Xray-core` | (نود روی `v26.7.28` پین است) | `5ca6f4b` | 2026-07-28 |
| `remnawave/asn-index` | — | `010924c` | 2026-06-25 |

اندازه‌گیری‌های عددی (اندازه‌ی ایندکس ASN، تعداد پیشوندها، هزینه‌ی lookup) روی artifactهای واقعی دانلودشده اجرا شد، نه تخمین.

**چیزی که انجام نشد:** طبق قرارداد `CLAUDE.md` هر endpoint باید در برابر OpenAPI زنده‌ی `{PANEL_BASE_URL}/api` تأیید شود. این نشست به پنل زنده دسترسی ندارد (`PANEL_BASE_URL`/`PANEL_API_TOKEN` در محیط نیست)، پس همه‌چیز از **قرارداد منبع** تأیید شده نه از پنل در حال اجرا. فهرست کامل در بخش ۱۰.

---

## ۲. سؤال ۱ — آیا Remnawave همین حالا بخشی از این داده را جمع می‌کند؟

**نه.** هیچ‌یک از پنج فیلد خواسته‌شده (ASN مبدأ، کد کشور کاربر، نوع transport، مدت نشست، حجم آپلود/دانلود per-connection) در پنل وجود ندارد.

### آنچه واقعاً ذخیره می‌شود

| جدول | کلید | محتوا | مرجع |
|---|---|---|---|
| `nodes_usage_history` | (nodeUuid, **ساعت**) | `downloadBytes` / `uploadBytes` / `totalBytes` | `prisma/schema.prisma:235` |
| `nodes_user_usage_history` | (nodeId, userId, **روز**) | `totalBytes` | `prisma/schema.prisma:218` |
| `user_traffic` | userId | `usedTrafficBytes`, `lifetimeUsed…`, `onlineAt`, `lastConnectedNodeUuid`, `firstConnectedAt` | `prisma/schema.prisma:86` |
| `config_profile_inbounds` | tag | `type`, `network`, `security`, `port` | `prisma/schema.prisma:416` |
| `nodes` | uuid | `countryCode` — **کشور نود، نه کاربر** | `prisma/schema.prisma:196` |

نکته‌ی مهم برای پروژه‌ی خودمان: `nodes_usage_history` **ساعتی** است. یعنی ادعای فعلی `CLAUDE.md` که «پنل ترافیک را فقط به‌صورت `nodes.totalBytesLifetime` — یک شمارنده‌ی تجمعی — گزارش می‌کند» درباره‌ی *endpointی که ما صدا می‌زنیم* درست است، ولی درباره‌ی *چیزی که پنل نگه می‌دارد* نه. این ربطی به این پروپوزال ندارد ولی ارزش یک نگاه جداگانه را دارد.

### جایی که پنل IP کاربر را **ذخیره می‌کند** (مهم برای محدودیت ۱)

سه جا، و هر سه روی دیسک:

1. `hwid_user_devices.requestIp` — `prisma/schema.prisma:342`
2. `user_subscription_request_history.requestIp` — `prisma/schema.prisma:498`
3. `torrent_blocker_reports.report` (JSON) — شامل `xrayReport.source` = `IP:port` کاربر، کنار `userId` — `prisma/schema.prisma:619`

و یک کانال چهارم، **اختیاری اما موجود**: با `EXPORT_TO_STREAM_ENABLED=true` پنل هر ۵ دقیقه از هر نود لیست IPهای آنلاین را می‌کشد و در یک **Redis Stream** می‌ریزد (`nodeId` + `users[{userId, ips[{ip,lastSeen}]}]`، نگهداری یک ساعت):
- زمان‌بند: `src/scheduler/enqueue/export-node-connections/export-node-connections.task.ts`
- پردازشگر: `src/queue/_nodes/processors/query-nodes.processor.ts:223-260`

**این نزدیک‌ترین چیز به «کانال تله‌متری آماده» است — و دقیقاً چیزی را صادر می‌کند که ما اجازه نداریم داشته باشیم: IP خام جفت‌شده با شناسه‌ی کاربر.** به‌عنوان منبع داده رد می‌شود، ولی به‌عنوان *الگو* (نود انباشت می‌کند، پنل pull می‌کند) دقیقاً همان چیزی است که خواهیم ساخت.

### ASN

نود **از قبل** یک پایگاه ASN دارد — این را انتظار نداشتم:

```dockerfile
ARG ASN_LMDB_URL=https://github.com/remnawave/asn-index/releases/latest/download/asn-prefixes-lmdb.tar.gz
COPY --from=xray /usr/local/share/asn /usr/local/share/asn
```
— `node/Dockerfile`

با یک سرویس آماده روی آن: `node/src/modules/asn-lmdb/asn-lmdb.service.ts`.

**اما جهتش برعکس است.** امضایش `getByAsn(asn: number) → {ipv4: string[], ipv6: string[]}` است — یعنی ASN→پیشوند، برای بلاک/اجازه‌ی کل یک ASN در nftables. ما IP→ASN می‌خواهیم. جزئیات در بخش ۵.

---

## ۳. سؤال ۲ — کانال ارتباطی پنل با نود

### پروتکل و احراز هویت

**HTTPS REST روی axios، با mTLS و JWT هم‌زمان:**

```ts
this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${jwt.jwtToken}`;
this.mtlsOptions = { cert: jwt.clientCert, key: jwt.clientKey, ca: jwt.caCert };
const httpsAgent = new https.Agent({
    ...this.mtlsOptions, rejectUnauthorized: true, keepAlive: true, minVersion: 'TLSv1.3',
});
```
— `backend/src/common/axios/axios.service.ts:79-107`

بدنه‌های بزرگ با zstd فشرده می‌شوند (`backend/src/common/axios/axios.service.ts:160-172`). Timeout پیش‌فرض ۴۵ ثانیه.

### جهت: **فقط pull. نود نمی‌تواند push کند.**

این قطعی است و از پیکربندی نود ثابت می‌شود — کل env نود این است:

```ts
NODE_PORT, SECRET_KEY, JWT_PUBLIC_KEY?, DISABLE_HASHED_SET_CHECK,
INTERNAL_REST_TOKEN, INTERNAL_SOCKET_PATH, XTLS_API_SOCKET_PATH
```
— `node/src/common/config/app-config/config.schema.ts`

**هیچ `PANEL_URL`ی وجود ندارد.** نود آدرس پنل را نمی‌داند. جست‌وجوی کل درخت نود برای هر فراخوانی HTTP خروجی (`axios|fetch|http.request|got|undici`) دقیقاً یک نتیجه دارد و آن هم در CLI محلی است (`node/src/bin/cli/cli.ts:41`). نود یک سرور محض است.

**پیامد معماری:** هر داده‌ای که روی نود تولید شود باید **روی خود نود انباشته شود** تا کسی بیاید و آن را بردارد. این دقیقاً همان کاری است که torrent-blocker می‌کند و الگویی است که باید تقلید کنیم.

### سطح API نود

`node/libs/contract/api/routes.ts` — ریشه `/node`:

- `/node/xray/*` — start, stop, health-check
- `/node/handler/*` — add/remove user(s)، شمارش کاربران inbound، **drop-users-connections**، **drop-ips**
- `/node/stats/*` — `get-users-stats`، `get-system-stats`، `get-inbound-stats`، `get-all-inbounds-stats`، `get-outbound-stats`، `get-all-outbounds-stats`، `get-combined-stats`، `get-user-online-status`، **`get-user-ip-list`**، **`get-users-ip-list`**
- `/node/plugin/*` — `sync`، `torrent-blocker/collect`، `nftables/{block-ips,unblock-ips,recreate-tables}`

و یک controller **داخلی** که فقط روی یک Unix socket می‌شنود (نه روی شبکه):

```ts
@Get(XRAY_INTERNAL_API_PATH)      // '/internal/get-config'  — Xray کانفیگش را از اینجا می‌گیرد
@Post(XRAY_INTERNAL_WEBHOOK_PATH) // '/internal/webhook'     — Xray رویدادهای اتصال را اینجا می‌ریزد
```
— `node/src/modules/internal/internal.controller.ts`

### زمان‌بندی pullهای موجود

```
NODE_HEALTH_CHECK        : هر ۱۰ ثانیه
RECORD_USER_USAGE        : هر ۱۵ ثانیه   → getUsersStats روی هر نود
RECORD_NODE_USAGE        : هر ۳۰ ثانیه
EXPORT_NODE_CONNECTIONS  : هر ۵ دقیقه    (فقط با EXPORT_TO_STREAM_ENABLED)
REVIEW_NODES             : هر ۱ ساعت
```
— `backend/src/scheduler/intervals.ts`

این عددها برای بخش ۷ مهم‌اند: پنل **همین حالا** هر ۱۵ ثانیه از هر نود آمار کاربران را می‌کشد. یک pull ساعتی اضافه در برابر این چیزی نیست.

---

## ۴. سؤال ۳ — Xray-core از طریق StatsService چه می‌دهد

### قرارداد کامل

```proto
service StatsService {
  rpc GetStats(GetStatsRequest) returns (GetStatsResponse) {}
  rpc GetStatsOnline(GetStatsRequest) returns (GetStatsResponse) {}
  rpc QueryStats(QueryStatsRequest) returns (QueryStatsResponse) {}
  rpc GetSysStats(SysStatsRequest) returns (SysStatsResponse) {}
  rpc GetStatsOnlineIpList(GetStatsRequest) returns (GetStatsOnlineIpListResponse) {}
  rpc GetAllOnlineUsers(GetAllOnlineUsersRequest) returns (GetAllOnlineUsersResponse) {}
  rpc GetUsersStats(GetUsersStatsRequest) returns (GetUsersStatsResponse) {}
}
```
— `Xray-core/app/stats/command/command.proto`

`GetUsersStats` پرمحتواترین است:

```proto
message UserStat {
  string email = 1;
  repeated OnlineIPEntry ips = 2;   // {ip, last_seen}
  TrafficUserStat traffic = 3;      // {uplink, downlink}
}
```

### پاسخ مستقیم: **فقط شمارنده‌ی تجمعی. هیچ داده‌ی per-connection نیست.**

نام شمارنده‌ها فقط سه شکل دارد:

```go
"user>>>"     + user.Email + ">>>traffic>>>uplink" | ">>>downlink"   // app/dispatcher/default.go:164,173
"inbound>>>"  + tag        + ">>>traffic>>>uplink" | ">>>downlink"   // app/proxyman/inbound/always.go:28,36
"outbound>>>" + tag        + ">>>traffic>>>uplink" | ">>>downlink"   // app/proxyman/outbound/handler.go:41,49
```

**دو محدودیت که مستقیماً طراحی پژوهش را عوض می‌کنند:**

1. **هیچ شمارنده‌ی بایت per-connection وجود ندارد.** بایت‌ها روی خودِ لینک با یک wrapper شمرده می‌شوند و مستقیم به شمارنده‌ی کاربر می‌روند.
2. **هیچ تفکیک (کاربر × inbound) وجود ندارد.** کاربری که هم‌زمان روی دو inbound است یک شمارنده‌ی مشترک دارد. جمع per-inbound هست، ولی روی همه‌ی کاربران.

**پیامد صریح: نمی‌شود «حجم آپلود/دانلود این نشست از این ASN» را از Xray درآورد.** بایت به کاربر نسبت داده می‌شود، و یک کاربر در طول شبانه‌روز می‌تواند از چند ASN وصل شود. هر عددی که «بایت per-ASN» ادعا کند یا سرشکن‌کردن حدسی است یا دروغ. این باید در پروپوزال صریح نوشته شود.

### مدت نشست از کجا می‌آید؟

Xray **می‌داند** یک اتصال کِی بسته می‌شود — ولی آن را جایی صادر نمی‌کند:

```go
func trackOnlineIP(ctx context.Context, sm stats.Manager, email, ip string) {
	name := "user>>>" + email + ">>>online"
	if om, _ := sm.GetOrRegisterOnlineMap(name); om != nil {
		om.AddIP(ip)
		context.AfterFunc(ctx, func() { om.RemoveIP(ip) })
	}
}
```
— `Xray-core/app/dispatcher/default.go:224-230`

`OnlineMap` **refcount** است: هر اتصال یک واحد اضافه می‌کند، بستن یک واحد کم می‌کند، و در صفر IP حذف می‌شود (`Xray-core/app/stats/online_map.go`). `lastSeen` زمان *آخرین باز شدن* است، نه آخرین بایت.

پس سه راه برای مدت نشست، و هیچ‌کدام رایگان نیست:

| راه | چه می‌دهد | هزینه |
|---|---|---|
| نمونه‌برداری از `GetStatsOnlineIpList` / `GetUsersStats` | **حضور** با دقت بازه‌ی نمونه‌برداری | نشستی که کوتاه‌تر از بازه باشد **اصلاً دیده نمی‌شود** |
| webhook قاعده‌ی مسیریابی (زیر) | زمان **باز شدن** | بسته شدن ندارد |
| access log | باز و بسته و بایت | **IP روی دیسک می‌نویسد → نقض محدودیت ۱** |

### کشف اصلی: webhook در سطح قاعده‌ی مسیریابی

Xray-core (نسخه‌ی v26 که نود روی آن پین است) یک فیلد `webhook` روی هر قاعده‌ی مسیریابی دارد:

```proto
message WebhookConfig {
  string url = 1;
  uint32 deduplication = 2;
  map<string, string> headers = 3;
}
// RoutingRule.webhook = 22
```
— `Xray-core/app/router/config.proto`

و از `PickRoute` شلیک می‌شود — یعنی **یک بار به ازای هر اتصالِ مسیریابی‌شده**:

```go
if rule.Webhook != nil {
    rule.Webhook.Fire(originalCtx, tag)
}
```
— `Xray-core/app/router/router.go:105-107`

بدنه‌ی رویداد (`Xray-core/app/router/webhook.go:21-35`):

```json
{ "email", "level", "protocol", "network", "source", "destination",
  "originalTarget", "routeTarget", "inboundTag", "inboundName",
  "inboundLocal", "outboundTag", "ts" }
```

**این دقیقاً همان جریان per-connection است که لازم داریم** — و Remnawave همین حالا از آن استفاده می‌کند، برای torrent-blocker:

- تزریق قاعده: `node/src/common/utils/generate-api-config.ts` + `node/libs/contract/constants/xray/stats.ts:43-52`
- گیرنده: `node/src/modules/internal/internal.controller.ts:33-36`
- مصرف‌کننده: `node/src/modules/_plugin/events/xray-webhook/xray-webhook.handler.ts`

#### چهار نکته‌ی ریز که اگر نادیده گرفته شوند داده را خراب می‌کنند

1. **`protocol` آن چیزی نیست که فکر می‌کنید.** این پروتکل **sniff‌شده‌ی لایه‌ی ۷** است (`tls` / `http` / `bittorrent` / `quic`) — `Xray-core/app/dispatcher/default.go:243` آن را از `result.Protocol()` سنیفر می‌گیرد، و `features/routing/session/context.go:115` همان را برمی‌گرداند. **VLESS/Trojan/Shadowsocks نیست.**
   نوع transport باید با join روی `inboundTag` از `config_profile_inbounds` گرفته شود، که `{type, network, security}` دارد (`prisma/schema.prisma:416`) — یعنی `vless` + `xhttp` + `reality` دقیقاً همان چیزی است که خواسته شده، ولی از سمت پنل می‌آید نه از خود اتصال.
2. **`email` = شناسه‌ی عددی کاربر پنل.** پنل موقع افزودن کاربر به نود `username: id.toString()` می‌فرستد (`backend/src/modules/nodes/events/add-user-to-node/add-user-to-node.handler.ts:66`). پس `email` یک شناسه‌ی دائمی و مستقیماً قابل اتصال به `users.telegram_id` است. **هر رکوردی که آن را نگه دارد محدودیت ۳ را نقض می‌کند.**
3. **`deduplication` روی `email` است، نه IP و نه inbound:**
   ```go
   if h.isDuplicate(email) { return }
   ```
   — `Xray-core/app/router/webhook.go:95`. با dedup فعال، «تعداد رویداد» **تعداد اتصال نیست** — «کاربرِ فعال در هر بازه‌ی dedup» است. و کاربری که هم‌زمان روی دو شبکه (مثلاً موبایل و وای‌فای) است، یکی از دو ASNش گم می‌شود.
4. **بایت و مدت در payload نیست.** رویدادِ *باز شدن* است. بایت باید از شمارنده‌های تجمعی بیاید و مدت از نمونه‌برداری — و هیچ‌کدام به این رویداد قابل چسباندن نیست.

### درباره‌ی access log (چرا نباید سراغش رفت)

پیام access با `From: connection.RemoteAddr()` ساخته می‌شود و برای اتصال پذیرفته‌شده `Email` هم دارد (`Xray-core/proxy/vless/inbound/inbound.go:601-607`، قالب در `Xray-core/common/log/access.go:33-58`). خروجی Xray در نود به `/var/log/xray/current` می‌رود (`node/rootfs/etc/s6-overlay/s6-rc.d/xray/run` + سرویس `xray-log`).

**یعنی روشن‌کردن `log.access` در config profile، IP کاربر را کنار شناسه‌اش روی دیسک نود می‌نویسد.** این مستقیماً محدودیت ۱ است. هر معماری‌ای که انتخاب شود باید صریح بگوید access log خاموش می‌ماند — و این باید در مستندات عملیاتی نوشته شود، نه فقط اینجا.

---

## ۵. سؤال ۴ — اطلاعات ASN

### آنچه نود از قبل دارد (و چرا کافی نیست)

`remnawave/asn-index`، روزانه ساعت ۰۴:۰۰ UTC از `ipverse/as-ip-blocks` (که خودش داده‌ی BGP عمومی را تجمیع می‌کند) ساخته می‌شود.

**اندازه‌گیری‌شده روی artifact واقعی:**

| معیار | مقدار |
|---|---|
| tarball | ۳٫۱۴ MB |
| LMDB بازشده | ۱۲٫۳ MB |
| تعداد ASN | **۸۶٬۳۸۶** |
| پیشوند IPv4 | **۴۱۷٬۰۰۸** |
| پیشوند IPv6 | **۹۴٬۹۴۲** |

پوشش ایران بررسی شد — همه‌ی ASNهای بزرگ حاضرند:

| ASN | پیشوند IPv4 |
|---|---|
| AS44244 (ایرانسل) | ۱۲ |
| AS58224 (مخابرات) | ۴۹۴ |
| AS197207 (همراه اول) | ۶۴ |
| AS16322 (پارس‌آنلاین) | ۱۰ |
| AS31549 (شاتل/آسیاتک) | ۲۴ |
| AS43754 (آسیاتک) | ۵۵ |
| AS12880 (DCI/ITC) | ۱۳ |
| AS50810 (مبین‌نت) | ۶۷ |
| AS206065 | ۱۰۲ |

**مشکل: جهت.** سرویس موجود فقط `getByAsn(asn) → {ipv4, ipv6}` است (`node/src/modules/asn-lmdb/asn-lmdb.service.ts:48-62`). ما `lookup(ip) → asn` می‌خواهیم.

### گزینه الف — معکوس‌کردن همان داده (توصیه‌شده)

۴۱۷ هزار پیشوند IPv4 به‌صورت آرایه‌ی مرتب `(start, end, asn)` با جست‌وجوی دودویی. **اندازه‌گیری شد:**

| معیار | مقدار |
|---|---|
| payload به‌صورت uint32 (۳×۴ بایت) | **۵٫۰۰ MB** |
| payload به‌صورت uint64 (که benchmark با آن اجرا شد) | ۱۰٫۰۱ MB |
| هزینه‌ی lookup | **۰٫۸۸ µs** — CPython با آرایه‌های C-backed، ۵۰۰ هزار lookup در ۰٫۴۴ ثانیه |

درستی روی لنگرهای شناخته‌شده تأیید شد: `1.1.1.1 → AS13335` (Cloudflare)، `8.8.8.8 → AS15169` (Google)، `2.144.0.1 → AS44244` (ایرانسل)، `5.160.0.1 → AS42337`.

۰٫۸۸ µs عدد CPython است؛ پیاده‌سازی Go یا Node قطعاً زیر آن می‌آید. **هزینه‌ی lookup در برابر هر چیز دیگری در مسیر ناچیز است.**

**مزیت‌ها:** بدون وابستگی جدید، بدون کلید لایسنس، داده از قبل روی نود است، همان چرخه‌ی به‌روزرسانی Remnawave.
**عیب‌ها:** ساخت ایندکس معکوس در startup چند ثانیه می‌گیرد (یا باید pre-build شود)؛ داده BGP-derived است نه ثبت رسمی.

### گزینه ب — GeoLite2-ASN یا معادل

| منبع | کلید لازم؟ | به‌روزرسانی |
|---|---|---|
| MaxMind GeoLite2-ASN | بله (رایگان، ثبت‌نام) | هفتگی، با `geoipupdate` |
| DB-IP ASN-lite | خیر | ماهانه |
| IPinfo Free ASN | بله (توکن رایگان) | روزانه |

قالب mmdb با mmap خوانده می‌شود، پس فضای آدرس مصرف می‌کند نه heap.

> ⚠️ **اندازه‌ی این‌ها تأیید نشد.** تلاش برای دانلود DB-IP ASN-lite از این محیط با HTTP 403 برخورد کرد (فیلتر proxy). هر عددی که برای اندازه‌ی GeoLite2-ASN بنویسم از حافظه است نه اندازه‌گیری، و طبق قرارداد پروژه چنین چیزی را نمی‌نویسم. اگر گزینه ب جدی شد، اول اندازه بگیرید.

### به‌روزرسانی و بازتولیدپذیری

نکته‌ای که برای یک دیتاست **پژوهشی** حیاتی است و راحت فراموش می‌شود:

**نگاشت IP→ASN با زمان تغییر می‌کند.** ISPهای ایران پیشوندها را جابه‌جا می‌کنند. یک رکورد که فقط `AS44244` را نگه دارد، شش ماه بعد قابل بازتولید نیست.

**هر ردیف تجمیع باید تاریخِ snapshot ایندکس ASN را که با آن حل شده حمل کند.** بدون آن، «چرا این ساعت AS58224 پرید» بین «ترافیک واقعاً جابه‌جا شد» و «BGP عوض شد» قابل تفکیک نیست — و همان اشتباهی است که `CLAUDE.md` درباره‌ی شمارنده‌ی تجمعی می‌گوید: مقدار خام را ذخیره کن، تفسیر را موقع خواندن انجام بده.

---

## ۶. سؤال ۵ — DPI: چه چیزی قابل اندازه‌گیری نیست، و جایگزین‌ها دقیقاً چه می‌گویند

### فرض شما درست است، و بدتر از چیزی است که نوشتید

اگر DPI اتصال را قبل از رسیدن به نود قطع کند، نود **هیچ چیز** نمی‌بیند. webhook از `PickRoute` شلیک می‌شود، که **بعد از** یک handshake پروکسی موفق است. یعنی هر رویدادی که ما ببینیم به‌طور تعریفی یک موفقیت است. **جامعه‌ی آماری‌ای که می‌بینیم فقط از بازماندگان تشکیل شده.**

مشکل عمیق‌تر: **صورت بدون مخرج.** «۱٬۲۰۰ اتصال موفق از AS44244 در ساعت ۲۰» یک *نرخ* نیست. بدون دانستن «چند نفر تلاش کردند»، ۱٬۲۰۰ هم می‌تواند ۹۹٪ موفقیت باشد و هم ۳٪.

### پنج سیگنالی که در دسترس هست — و مرز دقیق هرکدام

#### ۵.۱ اتصال موفق per-(ASN, ساعت, inbound)
*منبع:* webhook قاعده‌ی مسیریابی.

| ✅ می‌تواند نشان دهد | ❌ نمی‌تواند نشان دهد |
|---|---|
| کدام ASNها اصلاً کار می‌کنند | نرخ شکست |
| **سری زمانی یک ASN با خودش** — افت ناگهانی AS197207 در ساعت X سیگنال قوی است حتی بدون مخرج | آیا افت به‌خاطر بلاک است یا کاربران خواب بودند |
| مقایسه‌ی نسبیِ transportها **در همان ASN و همان ساعت** — اگر REALITY افت کند و XHTTP نکند، این یک یافته‌ی واقعی است | مقایسه‌ی مطلق بین ASNها (سهم بازار ISPها یکسان نیست) |

**قوی‌ترین شکل استفاده: مقایسه‌ی درون‌گروهی.** ASN را ثابت نگه دار، ساعت را ثابت نگه دار، transport را عوض کن. مخرج ناشناخته حذف می‌شود چون برای هر دو یکی است. این تنها استنتاج علّیِ محکمی است که از سمت نود درمی‌آید.

#### ۵.۲ توزیع مدت نشست
*منبع:* نمونه‌برداری از `GetUsersStats` / `GetStatsOnlineIpList`.

| ✅ | ❌ |
|---|---|
| نشست‌ها می‌مانند یا زود می‌میرند | **علت.** DPI؟ وای‌فای ضعیف؟ کاربر اپ را بست؟ توزیع هر سه را یکسان نشان می‌دهد |
| مقایسه‌ی توزیع بین transportها در همان ASN | تفکیک قطع‌شدن از بی‌کار ماندن |

**سقف روش، و باید صریح در پروپوزال بیاید:** `OnlineMap` وقتی refcount صفر شود IP را حذف می‌کند. **نشستی که کوتاه‌تر از بازه‌ی نمونه‌برداری باشد اصلاً دیده نمی‌شود.** یعنی *سریع‌ترین شکست‌ها — که دقیقاً امضای DPI هستند — نامرئی‌اند.* نمونه‌برداری ۶۰ ثانیه‌ای یک اتصال که بعد از ۸ ثانیه ریست شده را با اتصالی که هرگز برقرار نشده یکسان می‌بیند.

#### ۵.۳ نرخ قطع زودهنگام
همان محدودیت ۵.۲ با شدت بیشتر. با نمونه‌برداری ۱۰ ثانیه‌ای مفید می‌شود، ولی بار نمونه‌برداری ۶ برابر و هنوز کف دقتش ۱۰ ثانیه است. مقایسه‌ی نسبی بین transportها باز هم معتبر می‌ماند؛ عدد مطلق نه.

#### ۵.۴ `AccessRejected` در VLESS
```go
log.Record(&log.AccessMessage{ From: connection.RemoteAddr(), Status: log.AccessRejected, Reason: err })
```
— `Xray-core/proxy/vless/inbound/inbound.go:516-521`

| ✅ | ❌ |
|---|---|
| اتصالی به نود رسیده ولی handshake نامعتبر داشته — probe، اسکن فعال، کلاینت خراب | **DPI.** یک اتصال بلاک‌شده اصلاً نمی‌رسد که رد شود |

و فقط در **access log** موجود است، که IP را روی دیسک می‌نویسد. **رد می‌شود** — به‌خاطر محدودیت ۱، نه به‌خاطر بی‌فایده بودن.

#### ۵.۵ مخرج واقعی — از سمت خودمان، نه از نود

**این تنها راهی است که به «نرخ شکست» نزدیک می‌شود، و از نود نمی‌آید.**

ما `config_logs` را داریم — یک ردیف به ازای هر claim، با `location` و `created_at`. اگر در **لحظه‌ی claim** ASN درخواست‌کننده در حافظه محاسبه شود (دقیقاً همان انضباطی که `ip_bucket` در `backend/gozar/web/routes/public/identity.py:88-101` دارد — hash نمکی‌شده‌ی IP درشت‌شده، هرگز IP خام)، آنگاه:

```
شکست تحویل(ASN, ساعت) = claimها(ASN, ساعت) − کاربرانِ متمایزی که ظاهر شدند(ASN, ساعت+Δ)
```

| ✅ | ❌ |
|---|---|
| **مخرج واقعی**: چند نفر از AS44244 کانفیگ گرفتند اما هرگز روی نود ظاهر نشدند | «شکست دسترسی» — صفحه‌ی claim خودش از پشت همان DPI بار می‌شود. کسی که سایت/تلگرام برایش کار نمی‌کند در مخرج هم نیست |
| قابل تفکیک بر حسب location و transport | تفکیک «DPI بست» از «کاربر امتحان نکرد» |

**دو تله:**

1. **سوگیری بقا در خود مخرج.** آنچه اندازه می‌گیریم «شکست *بعد از* دریافت کانفیگ» است، نه «شکست دسترسی». باید با همین عبارت در مقاله نوشته شود، وگرنه عدد بیش از حد خوش‌بین است.
2. **محدودیت ۳.** ASNِ لحظه‌ی claim نباید کنار `telegram_id` نوشته شود. باید مستقیماً به یک شمارنده‌ی تجمیعی `(ساعت, ASN, location)` برود و IP و شناسه هر دو در همان درخواست دور ریخته شوند. **یک جدول staging با (telegram_id, asn) — حتی موقتی — نقض صریح است.**

### آنچه به هیچ روشی قابل اندازه‌گیری نیست

- بلاک SNI/REALITY قبل از رسیدن به نود
- throttling (کند شدن بدون قطع)
- تفاوت «DPI بست» و «کاربر بی‌خیال شد»
- هر چیزی درباره‌ی کاربرانی که هرگز به سایت یا بات نرسیدند

**اینها باید به‌عنوان محدودیت‌های صریح در پروپوزال بیایند، نه به‌عنوان کارِ آینده.**

---

## ۷. سؤال ۶ — توسعه‌پذیری Remnawave

### پنل: webhook خروجی رویداد

`WEBHOOK_ENABLED` / `WEBHOOK_URL` / `WEBHOOK_SECRET_HEADER` (حداقل ۳۲ کاراکتر الفبا-عددی، اجباری) — `backend/src/common/config/app-config/config.schema.ts:63-65,171-232`.

کاتالوگ رویدادها **ثابت** است (`backend/libs/contract/constants/events/events.ts`): `user.*`، `node.*`، `service.*`، `errors.*`، `crm.*`، `user_hwid_devices.*`، `torrent_blocker.*`.

**هیچ رویداد سطح اتصال ندارد** — تنها استثنا `torrent_blocker.report` است که کل payload وبهوک Xray (شامل IP مبدأ) را حمل می‌کند. بی‌فایده برای ما، مگر با تحریف بدخیمِ torrent-blocker که هر ترافیکی را «تخلف» علامت بزند تا گزارش تولید کند. **این کار را نکنید:** IP خام از نود عبور می‌کند و در `torrent_blocker_reports` روی دیسک پنل می‌نشیند (`prisma/schema.prisma:619`) — نقض هم‌زمان محدودیت ۱ و ۲ و ۳.

### پنل: صادرات به Redis Stream

`EXPORT_TO_STREAM_ENABLED` — تنها کانال «داده‌ی خام به بیرون». همان‌طور که بخش ۲ گفت، دقیقاً IP+userId می‌دهد. **رد.**

### نود: «plugin» بارگذارِ کد نیست

مجموعه‌ی کاملاً ثابت پنج‌تایی:

```ts
export interface IPlugins {
    ingressFilter: boolean; egressFilter: boolean;
    torrentBlocker: boolean; connectionDrop: boolean; preStart: boolean;
}
```
— `node/src/modules/_plugin/interfaces/plugins.interface.ts`

`pluginConfig` (JSON از پنل) با `NodePluginSchema` از پکیج `@remnawave/node-plugins` اعتبارسنجی می‌شود و هر چیز خارج از schema رد می‌شود (`node/src/modules/_plugin/plugin.service.ts:65-77`). `preStart` هم — که اسمش امیدوارکننده است — فقط پاک‌سازی سوکت می‌کند (`node/src/modules/_plugin/plugin.service.ts:149-161`)، نه اجرای فرمان دلخواه.

**نتیجه: هیچ hook رسمی‌ای برای «رویداد اتصال با ASN» وجود ندارد.**

### اما احتمالاً fork لازم نیست — و اینجا دلیلش است

سه چیز پشت سر هم:

1. **`WebhookConfig.url` هر URLی را می‌پذیرد** — HTTP معمولی یا Unix socket با نحو `@socket:/path` (`Xray-core/app/router/webhook.go:53-71`)، به‌علاوه‌ی headerهای دلخواه.
2. **`generateApiConfig` قواعد کاربر را دست‌نخورده عبور می‌دهد:**
   ```ts
   routing: {
       ...(config.routing || {}),
       rules: [ XRAY_ROUTING_RULES_MODEL,
                ...(config.routing?.rules ?? []).filter(r => r.outboundTag !== 'REMNAWAVE_API') ],
   },
   ```
   — `node/src/common/utils/generate-api-config.ts`. تنها قاعده‌ای که حذف می‌شود آن است که به `REMNAWAVE_API` می‌رود. **بقیه با همه‌ی فیلدهایشان — از جمله `webhook` — عبور می‌کنند.**
3. **پنل قواعد مسیریابی را اعتبارسنجی نمی‌کند.** `XRayConfig.validate()` فقط inboundها را چک می‌کند (network، protocol، tag، shadowsocks) — `backend/src/common/helpers/xray-config/xray-config.validator.ts:385-397`. قواعد routing فقط برای جایگزینی snippet پیمایش می‌شوند (همان‌جا `:327-337`). یک کلید `webhook` بی‌سروصدا عبور می‌کند.

**پس: یک قاعده‌ی مسیریابی که در config profile نوشته شود و `webhook` داشته باشد، باید تا خود Xray برسد و شلیک کند — بدون یک خط تغییر در کد Remnawave.** این را کد می‌گوید؛ باید روی یک نود واقعی تأیید شود (بخش ۱۰).

### اگر fork لازم شد، هزینه‌اش چیست

- `remnawave/node` یک NestJS/TypeScript با معماری CQRS است. تغییر ما (یک ماژول + یک route + تزریق قاعده) کوچک است، ولی **در فایل‌هایی می‌نشیند که upstream فعالانه دست می‌زند** (`generate-api-config.ts`، ثابت‌های Xray، ماژول plugin).
- سرعت انتشار بالاست: نود روی 3.0.0 و backend روی 3.2.1 است. هر انتشار یک rebase.
- **هزینه‌ی پنهان: image build خودمان.** Dockerfile نود Xray را از منبع می‌کشد و LMDB ASN را دانلود می‌کند. یک fork یعنی مالکیت آن pipeline، مالکیت وصله‌های امنیتی Xray، و از دست دادن `docker pull` ساده. برای یک تیم کوچک این هزینه‌ی جاری است نه یک‌باره.
- **و fork نود به‌تنهایی کافی نیست:** endpoint جدید هنوز باید کشیده شود. یا پنل هم fork شود (پرهزینه‌تر)، یا endpoint احراز هویت مستقلِ خودش را داشته باشد تا GozarX مستقیم آن را بکشد — چون GozarX به گواهی mTLS نود دسترسی ندارد (آن‌ها متعلق به پنل‌اند: `backend/src/common/axios/axios.service.ts:93-97`).

---

## ۸. سؤال ۷ — سربار روی نود

### webhook — تنها جایی که سربار واقعاً معنادار است

هر رویداد یک goroutine و یک HTTP POST با timeout ۵ ثانیه می‌سازد (`Xray-core/app/router/webhook.go:99-110,166-196`).

| سناریو | حجم | نظر |
|---|---|---|
| `deduplication: 0`، ۵۰۰ کاربر همزمان | یک مرورگر ده‌ها اتصال TCP در دقیقه می‌سازد → **ده‌ها هزار POST/دقیقه** | **غیرقابل قبول** |
| `deduplication: 60`، ۵۰۰ کاربر همزمان | حداکثر ۱ رویداد per user per دقیقه → **~۸ رویداد/ثانیه** | ناچیز |

**بهایی که برای dedup می‌دهیم داده است، نه فقط دقت:** dedup روی `email` است، پس با آن، آنچه می‌شماریم «کاربر فعال در بازه» است نه «تعداد اتصال»، و کاربرِ چند‌شبکه‌ای یکی از ASNهایش را از دست می‌دهد. **این باید در تعریف متغیرِ دیتاست نوشته شود، نه در پانویس.**

**خطر واقعی که راحت از قلم می‌افتد:** اگر گیرنده کند شود، Xray برای هر رویداد یک goroutine می‌سازد که تا ۵ ثانیه منتظر می‌ماند. زیر بار این goroutine انباشت می‌کند **داخل فرایند Xray**. گیرنده باید فوراً 200 برگرداند و در حافظه صف کند — هیچ کار همگامی، هیچ I/O دیسکی، هیچ چیزی که بتواند block شود.

### ASN lookup

اندازه‌گیری‌شده: **۰٫۸۸ µs، ۵ MB (uint32)**. در برابر خودِ POST گم می‌شود.

### تجمیع در حافظه

کلید `(ساعت, ASN, inboundTag)`. با ۸۶ هزار ASN در پایگاه ولی عملاً چند ده ASN فعال، سطل‌ها **چند KB**اند نه چند MB.

### pull اضافه از پنل/GozarX

پنل همین حالا هر ۱۰ ثانیه health، هر ۱۵ ثانیه `getUsersStats` و هر ۳۰ ثانیه usage نود را می‌کشد (`backend/src/scheduler/intervals.ts`). **یک pull ساعتی زیر نویز است.**

### جمع‌بندی سربار

**با `deduplication` معقول، سربار ناچیز است.** بدون آن معنادار است. یک عدد پیکربندی، و طرف اشتباهش نود را زیر بار می‌برد.

---

## ۹. سه معماری

### معماری الف — سرویس تجمیع کنار نود، تغذیه از webhook خودِ Xray (بدون fork) ✅ توصیه‌شده

```
Xray (قاعده‌ی مسیریابی با webhook, dedup=60s)
   │  POST /ingest  ← IP مبدأ، email، inboundTag، ts
   ▼
gozar-asn-agent  (فرایند کوچک روی همان هاست، فقط localhost)
   │  در حافظه:  IP → ASN → دور ریختن IP  (هرگز هیچ‌جا نوشته نمی‌شود)
   │             email → HMAC با کلید per-hour در RAM، فقط برای distinct-count → دور ریختن
   │             سطل (ساعت, ASN, کد کشور, inboundTag) → {اتصال, کاربر متمایز}
   │  در پایان هر ساعت: سطل‌های زیر آستانه در «سایر» ادغام، کلید HMAC نابود می‌شود
   ▼  GET /buckets?hour=…  (توکن bearer، فقط localhost یا mTLS)
GozarX arq worker (pull ساعتی) → جدول جدید asn_telemetry
```

| محدودیت | وضعیت |
|---|---|
| ۱ — هیچ IP ذخیره نشود | ✅ IP فقط در حافظه‌ی agent، در همان تابع دور ریخته می‌شود. **مشروط به**: access log خاموش، سطح log نود روی debug نباشد |
| ۲ — تبدیل روی نود و در حافظه | ✅ دقیقاً همین |
| ۳ — غیرقابل اتصال به هویت | ⚠️ **نیازمند دقت.** `email` در payload شناسه‌ی عددی کاربر است. باید فقط برای شمارش distinct استفاده شود، با HMACِ کلیدِ ساعتیِ درون‌حافظه‌ای، و **هرگز** در خروجی نیاید. خروجی فقط شمارنده است |
| ۴ — آستانه‌ی k | ✅ ادغام قبل از تحویل، روی خود agent — پس داده‌ی زیرآستانه هرگز از نود خارج نمی‌شود |

**مزایا**
- بدون fork، بدون image سفارشی، بدون rebase
- IP هرگز نود را ترک نمی‌کند — نه در شبکه، نه روی دیسک
- k-anonymity **در مبدأ** اعمال می‌شود، نه در مقصد. این قوی‌ترین شکل رعایت محدودیت ۴ است
- سطح API کوچک؛ اگر Remnawave شکست، فقط agent متوقف می‌شود و بس

**معایب**
- **بایت و مدت نشست ندارد.** webhook فقط رویداد باز شدن است. برای این دو باید agent خودش `GetUsersStats` را نمونه‌برداری کند — که یعنی باید به سوکت gRPC داخلی Xray (`XTLS_API_SOCKET_PATH`) برسد. آن سوکت abstract Unix است داخل container نود، پس agent باید **در همان container یا با namespace مشترک** باشد. **این پیچیدگی عملیاتی واقعی است و مهم‌ترین چیزی است که باید در PoC اثبات شود.**
- به رفتاری تکیه دارد که مستند نیست (عبور دست‌نخورده‌ی قواعد routing). `generateApiConfig` می‌تواند در نسخه‌ی بعدی سخت‌گیرتر شود
- ازای هر نود یک استقرار

### معماری ب — fork کردن `remnawave/node`

یک ماژول تله‌متری داخل نود، با استفاده‌ی مستقیم از `AsnLmdbService` و `XtlsApi` موجود، و یک route جدید `/node/stats/asn-buckets`.

| محدودیت | وضعیت |
|---|---|
| ۱ | ✅ |
| ۲ | ✅ |
| ۳ | ✅ (کنترل کامل روی چرخه‌ی حیات email) |
| ۴ | ✅ |

**مزایا**
- بایت و مدت نشست **بدون هیچ ترفندی** در دسترس است — `XtlsApi` از قبل تزریق شده و به همان سوکتی وصل است که لازم داریم
- به رفتار مستندنشده تکیه نمی‌کند
- تمیزترین کد

**معایب**
- **هزینه‌ی نگهداری بالاترین.** rebase به ازای هر انتشار، در فایل‌هایی که upstream فعالانه تغییر می‌دهد
- مالکیت pipeline ساخت image (Xray از منبع + دانلود LMDB ASN)، از جمله وصله‌های امنیتی Xray
- **fork نود به‌تنهایی کافی نیست** — endpoint جدید باید کشیده شود؛ GozarX گواهی mTLS نود را ندارد، پس یا پنل هم fork می‌شود یا endpoint احراز هویت مستقل می‌خواهد
- کندترین مسیر تا اولین داده

### معماری ج — بدون تغییر نود: pull لیست IP از پنل ❌ رد

GozarX `connections-by-node` را از پنل بکشد (`backend/src/modules/connections/connections.service.ts:130-160`) یا Redis Stream را مصرف کند، و ASN را سمت خودش حل کند.

| محدودیت | وضعیت |
|---|---|
| ۱ | ❌ IP خام وارد فرایند GozarX می‌شود |
| ۲ | ❌ تبدیل روی نود نیست؛ IP از شبکه عبور می‌کند و در Redis می‌نشیند |
| ۳ | ❌ payload جفتِ (userId, IP) است |
| ۴ | ⚠️ فقط بعد از اینکه داده‌ی زیرآستانه از قبل حرکت کرده |

**بی‌قید و شرط رد.** طبق صورت مسئله گزارش می‌شود نه پیشنهاد. تنها چیز ارزشمندش این است که نشان می‌دهد Remnawave چطور یک مسئله‌ی *مشابه* را حل کرده — الگوی «نود انباشت می‌کند، پنل pull می‌کند» درست است؛ فقط payloadش غلط است.

---

## ۱۰. توصیه‌ی نهایی

**معماری الف، در دو فاز.**

### فاز ۰ — قبل از هر خط کد، سه چیز را روی یک نود واقعی اثبات کنید

۱. یک قاعده‌ی مسیریابی با `webhook` در config profile بنویسید و **تأیید کنید که به Xray می‌رسد و شلیک می‌کند**. کل معماری الف روی همین یک ادعا ایستاده و ادعا از خواندن کد آمده نه از اجرا.
۲. **تأیید کنید که agent می‌تواند به `XTLS_API_SOCKET_PATH` برسد.** اگر نتواند، بایت و مدت نشست از سمت agent در دسترس نیست و باید بین «فقط شمارش اتصال» و معماری ب انتخاب کنید. این یک بررسی نیم‌ساعته است که یک تصمیم دو‌هفته‌ای را تعیین می‌کند.
۳. **تأیید کنید که به shell خود نود دسترسی داریم.** اگر نه، هر سه معماری می‌میرند و فقط بخش ۵.۵ باقی می‌ماند.

### فاز ۱ — چیزی که ارزشمندترین داده را زودترین می‌دهد

- webhook با `deduplication: 60`
- agent فقط با تجمیع `(ساعت, ASN, کد کشور, inboundTag)` → `{اتصال, کاربر متمایز}`
- ادغام k-anonymity **روی agent**، قبل از اینکه هر چیزی نود را ترک کند
- **در کنارش، شمارنده‌ی claim per-ASN از سمت خودمان (بخش ۵.۵)** — این مخرج است، و بدون آن اعداد نود یک عدد بی‌جفت‌اند

### دلایل

1. **بدون fork است و ریسک نگهداری نمی‌سازد.** برای یک تیم کوچک با یک بات زنده، پذیرفتن هزینه‌ی rebase دائمی برای یک دیتاست پژوهشی معامله‌ی بدی است.
2. **محدودیت ۴ را در مبدأ اعمال می‌کند.** ادغام روی خود نود یعنی داده‌ی زیرآستانه هرگز از هاست خارج نمی‌شود. این تفاوت بین «ما ناشناس‌سازی می‌کنیم» و «داده‌ی قابل شناسایی هرگز وجود نداشت» است — و برای بازبینی اخلاقی یک پروپوزال پژوهشی، دومی چیزی است که می‌خواهید بنویسید.
3. **ارزشمندترین سیگنال ارزان‌ترین هم هست.** مقایسه‌ی درون‌گروهی (ASN ثابت، ساعت ثابت، transport متغیر) فقط شمارش اتصال می‌خواهد. بایت و مدت نشست گران‌ترند و — به‌خاطر محدودیت‌های بخش ۴ — از هر دو ضعیف‌تر تفسیر می‌شوند.
4. **fork هر وقت لازم شد در دسترس است.** اگر فاز ۰ شکست خورد یا مدت نشست ضروری شد، معماری ب باقی است و agentِ نوشته‌شده بیشترش قابل انتقال است.

### دو چیزی که باید در خودِ پروپوزال بیایند، نه در «کار آینده»

- **«بایت per-ASN» با این معماری وجود ندارد** و با هیچ معماری‌ای که Xray-core بدهد وجود نخواهد داشت. بایت‌ها به کاربر نسبت داده می‌شوند نه به اتصال (بخش ۴). هر عددی که ادعایش کند سرشکن‌کردن حدسی است.
- **جامعه‌ی آماری فقط از بازماندگان تشکیل شده.** حتی با مخرجِ بخش ۵.۵، آنچه اندازه می‌گیریم «شکست بعد از دریافت کانفیگ» است نه «شکست دسترسی».

---

## ۱۱. چیزهایی که نتوانستم قطعی جواب بدهم

هر کدام با روش قطعی‌کردنش:

| # | نامعلوم | چرا | چطور حل شود |
|---|---|---|---|
| ۱ | **آیا به shell نودها دسترسی داریم؟** | خارج از کد؛ در مخزن پیدا نیست | سؤال از مالک. **این را اول بپرسید — هر سه معماری به آن بستگی دارند** |
| ۲ | آیا `webhook` در قاعده‌ی مسیریابیِ نوشته‌شده در پنل واقعاً به Xray می‌رسد؟ | از خواندن `generateApiConfig` + validator نتیجه گرفته شد، اجرا نشد | فاز ۰ گام ۱ |
| ۳ | آیا یک فرایند جانبی می‌تواند به `XTLS_API_SOCKET_PATH` برسد؟ | به namespace/استقرار container بستگی دارد، نه به کد | فاز ۰ گام ۲ |
| ۴ | **هیچ endpointی در برابر OpenAPI زنده تأیید نشد** | این نشست `PANEL_BASE_URL`/`PANEL_API_TOKEN` ندارد | طبق قرارداد `CLAUDE.md` قبل از سیم‌کشی هر endpoint، در برابر `{PANEL_BASE_URL}/api` تأیید شود |
| ۵ | اندازه‌ی GeoLite2-ASN / DB-IP ASN-lite | دانلود از این محیط HTTP 403 گرفت (فیلتر proxy) | فقط اگر گزینه ب جدی شد؛ اندازه بگیرید، از حافظه ننویسید |
| ۶ | آیا `deduplication` روی UDP هم مثل TCP رفتار می‌کند؟ | `PickRoute` برای هر «نشست» صدا زده می‌شود؛ تعریف نشست برای UDP با TCP فرق دارد و تفاوتش پیگیری نشد | با ترافیک واقعی QUIC اندازه بگیرید |
| ۷ | نرخ واقعی رویداد روی ترافیک ما | ارقام بخش ۸ از منطق dedup محاسبه شده، نه از مشاهده | یک ساعت روی یک نود با `deduplication: 60` اجرا و رویدادها را بشمارید |
| ۸ | آیا REALITY موقع شکست handshake چیزی log می‌کند که از ترافیک عادی قابل تفکیک باشد؟ | فقط مسیر VLESS تا `AccessRejected` دنبال شد؛ مسیر fallback خود REALITY خوانده نشد | فقط اگر ۵.۴ ارزش پیگیری داشت — که به‌خاطر محدودیت ۱ ندارد |
| ۹ | آیا نودها ما را با `hasCapNetAdmin()` آنلاین‌ردیابی می‌کنند؟ | `statsUserOnline` روی `hasCapNetAdmin()` شرطی است (`node/src/common/utils/generate-api-config.ts`). بدون CAP_NET_ADMIN، **`GetStatsOnlineIpList` خالی است** | روی نود واقعی چک کنید — اگر خاموش باشد، مدت نشست حتی با نمونه‌برداری هم در دسترس نیست |

**مورد ۹ را دست‌کم نگیرید.** اگر container نود بدون `CAP_NET_ADMIN` اجرا شود، ردیابی آنلاین کاملاً خاموش است و مسیر «نمونه‌برداری برای مدت نشست» قبل از شروع مرده است.

---

## ۱۲. ضمیمه — نقشه‌ی مراجع

| موضوع | فایل |
|---|---|
| کانال پنل→نود (mTLS + JWT) | `backend/src/common/axios/axios.service.ts:79-107` |
| نود آدرس پنلی ندارد | `node/src/common/config/app-config/config.schema.ts` |
| سطح REST نود | `node/libs/contract/api/routes.ts` |
| ورودی داخلی webhook Xray | `node/src/modules/internal/internal.controller.ts:33-36` |
| تزریق قاعده‌ی webhook | `node/src/common/utils/generate-api-config.ts` · `node/libs/contract/constants/xray/stats.ts:43-52` |
| شمای payload وبهوک (سمت نود) | `node/libs/contract/models/xray-webhook.schema.ts` |
| پیاده‌سازی webhook (سمت Xray) | `Xray-core/app/router/webhook.go` · `Xray-core/app/router/config.proto` · `Xray-core/app/router/router.go:105-107` |
| قرارداد StatsService | `Xray-core/app/stats/command/command.proto` |
| نام‌گذاری شمارنده‌ها | `Xray-core/app/dispatcher/default.go:164-217` · `app/proxyman/inbound/always.go:28` |
| refcount آنلاین (IP) | `Xray-core/app/stats/online_map.go` · `app/dispatcher/default.go:224-230` |
| protocol = پروتکل sniff‌شده | `Xray-core/app/dispatcher/default.go:243` · `features/routing/session/context.go:115` |
| access log شامل IP | `Xray-core/proxy/vless/inbound/inbound.go:601-607` · `common/log/access.go:33-58` |
| سرویس ASN LMDB (جهت اشتباه) | `node/src/modules/asn-lmdb/asn-lmdb.service.ts` |
| منبع ASN + چرخه‌ی به‌روزرسانی | `remnawave/asn-index` — روزانه ۰۴:۰۰ UTC از `ipverse/as-ip-blocks` |
| مجموعه‌ی ثابت plugin | `node/src/modules/_plugin/interfaces/plugins.interface.ts` · `plugin.service.ts:65-77` |
| کاتالوگ رویداد پنل | `backend/libs/contract/constants/events/events.ts` |
| صادرات به Redis Stream | `backend/src/queue/_nodes/processors/query-nodes.processor.ts:223-260` |
| زمان‌بندی cronها | `backend/src/scheduler/intervals.ts` |
| مدل‌های ذخیره‌سازی | `backend/prisma/schema.prisma:86,164,218,235,342,416,498,619` |
| اعتبارسنجی config (routing چک نمی‌شود) | `backend/src/common/helpers/xray-config/xray-config.validator.ts:327-337,385-397` |
| email = شناسه‌ی عددی کاربر | `backend/src/modules/nodes/events/add-user-to-node/add-user-to-node.handler.ts:66` |
| سابقه‌ی IP-hashing خودمان | `backend/gozar/web/routes/public/identity.py:88-101` |
