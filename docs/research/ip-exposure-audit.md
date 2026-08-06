# حسابرسی نشت IP کاربران — استقرار فعلی

> **هیچ تغییری اعمال نشده.** این سند فقط خواندن است. هیچ env، دیتابیس، فایل کانفیگ یا
> ردیفی لمس نشد و هیچ داده‌ای حذف نشد. همه‌ی اصلاح‌ها **پیشنهاد**اند و منتظر تأیید.

> **رعایت بند ۳:** در این گزارش هیچ IP واقعی، هیچ UUID، هیچ آیدی تلگرام و هیچ محتوای ردیفی
> نیامده — فقط ساختار، نام ستون، و مسیر. این رعایت آسان بود چون این نشست **اصلاً دسترسی
> خواندن به داده‌ی زنده ندارد** (زیر را ببینید)، پس هیچ مقدار واقعی‌ای اساساً در دسترس نبود.

---

## ۰. دامنه‌ی کار — چه چیزی دیدم و چه چیزی ندیدم

این کانتینر یک clone تازه از مخزن است، **نه سرور پروداکشن**. تأیید شد:

| چیز | وضعیت |
|---|---|
| فایل `.env` | ندارد (فقط `.env.example`) |
| سوکت Docker | ندارد |
| دسترسی به `gozarx.gozarxservices.com` | مسدود (proxy با 403 رد می‌کند) |
| دسترسی به پنل Remnawave | ندارد (بدون `PANEL_BASE_URL`/`PANEL_API_TOKEN`) |
| دسترسی shell به نودها | ندارد |

پس یافته‌ها به دو دسته تقسیم می‌شوند و در کل سند با همین دو نشان مشخص شده‌اند:

- 🟢 **اثبات‌شده از کد** — قطعی. کد این کار را می‌کند، هر که استقرارش داده باشد.
- 🟡 **وابسته به استقرار** — کد مسیر را می‌سازد، ولی اینکه *الان روشن است یا نه* یک مقدار
  زنده است. برای هرکدام یک دستور **فقط-خواندنی** در بخش ۵ آمده.

**هیچ ادعایی درباره‌ی «الان چند ردیف هست» نمی‌کنم، چون نمی‌توانم بشمارم.** جایی که تعداد
لازم است، دستور شمارش داده شده — نه حدس.

---

## ۱. جدول اصلی

| # | محل | نوع داده | به هویت وصل است؟ | Retention | چه کسی می‌خواند |
|---|---|---|---|---|---|
| **A** | `site_devices.ip_bucket` (Postgres، `String(64)`) | SHA-256 نمکی‌شده‌ی **/24** (v4) یا **/48** (v6) — نه IP خام | 🔴 **بله، مستقیم** — همان ردیفِ دستگاه است | 🔴 **برای همیشه.** فقط با ریست دستی خود کاربر حذف می‌شود. هیچ cron پاک‌سازی وجود ندارد | پنل ادمین (لیست دستگاه‌ها + تحلیل «سطل‌های مشترک»)، هر کسی با دسترسی DB، **و بکاپ شبانه** |
| **B** | کلیدهای Redis: `site:rl:{claim_ip,contact_ip,push_sub_ip,transfer_create_ip,transfer_redeem,device_reset}:<IP>` | 🔴 **IP خام، عیناً داخل نام کلید** | 🟠 نه مستقیم — ولی کلید دوقلوی device-keyed در همان درخواست و با همان TTL نوشته می‌شود، پس هم‌زمانی قابل تطبیق است | کلید: ۶۰ ثانیه تا ۱ ساعت (TTL پنجره). **AOF: تا بازنویسی بعدی** (`--appendonly yes` + والیوم `redis_data`) | هر کسی با دسترسی به Redis یا والیومش |
| **C** | لاگ دسترسی nginx → stdout کانتینر → درایور json-file داکر روی دیسک هاست | 🟡 `$remote_addr` = IP لبه‌ی Cloudflare (نه کاربر) **اگر** DNS واقعاً Proxied باشد. قالب پیش‌فرض بسته‌ی nginx معمولاً `$http_x_forwarded_for` هم دارد — که Cloudflare با **IP واقعی کاربر** پرش می‌کند | 🟠 نه مستقیم؛ ولی مسیر درخواست (`/api/claim` و…) کنارش است | 🔴 **نامحدود** — نه `access_log` صریحی هست، نه `logging:` در compose، نه چرخش | root روی هاست، هر کسی با دسترسی به `/var/lib/docker/containers/` |
| **D** | Cloudflare Turnstile — پارامتر `remoteip` | 🔴 **IP خام، ارسال به شخص ثالث** | 🟠 با توکن Turnstile و کلید سایت، نه با هویت داخلی ما | سیاست نگهداری Cloudflare — خارج از کنترل ما | Cloudflare |
| **E** | خود Cloudflare (DNS به‌صورت Proxied) | 🔴 IP خام هر درخواست | 🟠 با درخواست HTTP، شامل کوکی دستگاه | سیاست Cloudflare | Cloudflare |
| **F** | بکاپ شبانه‌ی pg_dump → کانال تلگرام | فقط ستون `ip_bucket` (هش) — **نمک همراهش نیست** | 🔴 بله (کل جدول `site_devices`) | 🔴 **برای همیشه، در ابر تلگرام.** هیچ چیزی پیام‌های کانال را منقضی نمی‌کند | هر کسی با دسترسی به آن کانال تلگرام |
| **G** | `hwid_user_devices.request_ip` (Postgres **Remnawave**) | 🔴 **IP خام** | 🔴 **بله** — کلید اصلی `(hwid, user_id)` | 🔴 **برای همیشه.** تنها حذف، اقدام دستی ادمین است | ادمین‌های پنل Remnawave، هر کسی با دسترسی به DB پنل |
| **H** | `user_subscription_request_history.request_ip` (Postgres Remnawave) | 🔴 **IP خام** | 🔴 **بله** — `user_id` روی همان ردیف | 🟠 **۲۴ ردیف آخر به‌ازای هر کاربر**، بدون سقف زمانی. یعنی همیشه ۲۴ IP آخر هر کاربر موجود است | همان بالا |
| **I** | `torrent_blocker_reports.report` (JSONB، Remnawave) | 🔴 **`IP:port` خام** داخل `xrayReport.source` | 🔴 **بله** — ستون `user_id` روی همان ردیف | 🔴 **برای همیشه** تا truncate دستی | همان بالا |
| **J** | استریم‌های Redis پنل: `ioraw:export:node_connections` و `ioraw:export:subscription_requests` | 🔴 **IP خام جفت‌شده با `userId`** | 🔴 **بله، صریح** | node_connections: ۱ ساعت (MINID). subscription_requests: `EXPORT_TO_STREAM_MAXLEN` | هر مصرف‌کننده‌ی آن Redis. **خود Remnawave هیچ‌وقت این استریم‌ها را نمی‌خواند** |
| **K** | لاگ Xray روی هر نود: `/var/log/xray/current` | 🔴 **IP مبدأ + `email` = شناسه‌ی عددی کاربر پنل** | 🔴 **بله، در یک خط** | 🟢 **۱۰ MB چرخشی، بدون آرشیو** (`s6-log -b n0 s10485760`) | root روی نود |

---

## ۲. جزئیات هر مورد + کمترین تغییر ممکن

### A — `site_devices.ip_bucket`

🟢 **اثبات‌شده از کد.** `backend/gozar/web/routes/public/identity.py:88-101` و `:186`.

```python
def _coarse_ip(ip): → /24 (v4) یا /48 (v6)
def ip_bucket(request, secret): sha256(f"{secret}:{coarse}").hexdigest()[:64]
```

نمک `settings.site_cookie_secret` است — **همان کلیدی که کوکی دستگاه را امضا می‌کند**.
فقط موقع **ساخت** دستگاه نوشته می‌شود (`get_or_create`)، نه در بازدیدهای بعدی.

**آنچه این را از «نشت IP» جدا نگه می‌دارد، تنها یک چیز است: نمک.** فضای /24 در IPv4 فقط
~۱۶٫۷ میلیون حالت دارد؛ با داشتن نمک، برگرداندن **هر** `ip_bucket` به /24ش چند ثانیه کار
یک CPU است. تأیید شد که نمک فقط در `.env` (chmod 600، `install.sh:309`) است و **در هیچ
ردیف دیتابیسی نیست** — یعنی در بکاپ هم نیست. این تفکیک باید حفظ شود.

**کمترین تغییر:** نمک جدا. یک `SITE_IP_SALT` مستقل از `SITE_COOKIE_SECRET`، که در بکاپ و
لاگ هیچ‌وقت ظاهر نمی‌شود. (تغییر نمک، سطل‌های موجود را از سطل‌های جدید جدا می‌کند.)

**چه می‌شکند:** تشخیص سوءاستفاده. `top_ip_buckets` («این سطل چند دستگاه دارد») و فیلتر
`?ip_bucket=` در صفحه‌ی دستگاه‌های پنل روی همین ستون کار می‌کنند
(`web/routes/admin/site_stats.py:291`، `site_devices.py:111-122`،
`db/repositories/site_device.py:180-186`). با تغییر نمک، دستگاه‌های قدیم و جدید دیگر در
یک سطل نمی‌افتند تا وقتی دستگاه‌های قدیمی طبیعی منقضی شوند.

**پیشنهاد جایگزین (بی‌شکست):** یک retention روی خود ستون — `ip_bucket` را برای دستگاه‌هایی
که مثلاً ۹۰ روز `last_seen_at` نداشته‌اند `NULL` کن. سیگنال ضدسوءاستفاده فقط برای
دستگاه‌های *فعال* معنا دارد؛ سطل یک دستگاه خفته هیچ‌وقت خوانده نمی‌شود.

---

### B — IP خام داخل کلیدهای Redis

🟢 **اثبات‌شده از کد. این یک اشکال واقعی است، نه یک طراحی.**

```python
def site_ratelimit_key(bucket, identifier):
    """... an ``identifier`` (device uuid or IP bucket)."""   # ← داکستر می‌گوید bucket
    return f"site:rl:{bucket}:{identifier}"
```
— `backend/gozar/cache/redis.py:94-97`

اما **هر شش فراخوان `client_ip(request)` خام می‌فرستند، نه `ip_bucket(...)`**:

| فایل | خط |
|---|---|
| `web/routes/public/claim.py` | 116 |
| `web/routes/public/contact.py` | 71 |
| `web/routes/public/push.py` | 77 |
| `web/routes/public/transfer.py` | 68 |
| `web/routes/public/transfer.py` | 91 |
| `web/routes/public/device.py` | 48 |

یعنی داکسترینگ می‌گوید «IP bucket» و کد `ip_bucket` را دارد و می‌سازد — ولی هیچ‌کدام از
این شش نقطه از آن استفاده نمی‌کنند. **نیت در همان فایل نوشته شده و پیاده نشده.**

**پایداری:** Redis با `--appendonly yes` و والیوم `redis_data` بالا می‌آید
(`docker-compose.yml`). کلید TTL دارد (۶۰ ثانیه تا ۱ ساعت)، ولی **دستور `SET` که نام کلید
را در خود دارد در AOF می‌ماند** تا بازنویسی بعدی AOF. یعنی IPها روی دیسک هاست‌اند، برای
مدتی نامعین ولی محدود.

**کمترین تغییر ممکن — و بی‌هیچ شکستی:** در هر شش نقطه `client_ip(request)` را با
`ip_bucket(request, secret)` عوض کن.

**چه می‌شکند: عملاً هیچ.** محدودسازی نرخ به یک کلید *پایدار به‌ازای هر گروه* نیاز دارد، نه
به IP خواناپذیر. تنها تغییر رفتاری این است که پنجره از «هر IP» به «هر /24» می‌رود — یعنی
یک شبکه‌ی خانگی پشت NAT به‌جای اینکه هر عضوش سهم خودش را داشته باشد یک سهم مشترک می‌گیرد.
سقف‌های فعلی (۴۰ claim/دقیقه، ۶۰ push/ساعت، ۳۰ contact/ساعت) به‌قدری بالا هستند که این
تفاوت برای کاربر عادی محسوس نیست — و در برابر مزرعه‌ی حساب، /24 در واقع **سیگنال بهتری**
است، چون همان چیزی است که `top_ip_buckets` را می‌سازد.

**نکته:** این تغییر داکسترینگ موجود را *درست* می‌کند، نه اینکه رفتار جدیدی بیاورد.

---

### C — لاگ دسترسی nginx

🟢 **اثبات‌شده:** نه `nginx/nginx.conf` و نه بخش تولید `nginx.tls.conf` در `install.sh` هیچ
دستور `access_log`ی ندارند → پیش‌فرض ایمیج اعمال می‌شود. تأیید شد که ایمیج رسمی
`/var/log/nginx/access.log` را به `/dev/stdout` symlink می‌کند
(`nginx/docker-nginx` → `stable/debian/Dockerfile:133`). `docker-compose.yml` هیچ بخش
`logging:` ندارد → درایور پیش‌فرض `json-file` **بدون `max-size`/`max-file`** → روی دیسک
هاست، **بدون چرخش، برای همیشه**.

🟡 **آنچه باید روی سرور تأیید شود:** قالب لاگ. nginx در سورس `log_format main` را
کامنت‌شده دارد (`nginx/conf/nginx.conf:21`)، ولی بسته‌ی رسمی معمولاً آن را فعال می‌کند و آن
قالب `"$http_x_forwarded_for"` دارد. **این تفاوت مهم است:**

- اگر `$http_x_forwarded_for` در قالب نباشد → لاگ فقط IP لبه‌ی Cloudflare را دارد. کم‌خطر.
- اگر باشد → Cloudflare این هدر را با **IP واقعی کاربر** پر می‌کند و لاگ IP کاربر را دارد.

دستور تأیید در بخش ۵ (مورد ۵.۴).

**کمترین تغییر (هر دو حالت):** در هر دو `server` بلوک `access_log off;` بگذار — یا اگر لاگ
لازم است، یک `log_format` بدون هیچ فیلد IP تعریف کن.

**چه می‌شکند:** عیب‌یابی. لاگ ۴۰۴/۵۰۲ و «چه کسی این را زد» از بین می‌رود. اگر لاگ لازم
است، حداقلِ بی‌ضرر: `error_log` را نگه دار و فقط `access_log` را خاموش کن.

**تغییر مکمل (مستقل و بی‌شکست):** به compose برای همه‌ی سرویس‌ها اضافه کن:
```yaml
logging: { driver: json-file, options: { max-size: "10m", max-file: "3" } }
```
این چرخش را می‌گذارد بدون اینکه چیزی را خاموش کند — و روی *همه‌ی* کانتینرها اثر دارد، نه
فقط nginx.

---

### D — Turnstile

🟢 `backend/gozar/web/routes/public/security.py:34` — `data={"secret":…, "response": token,
"remoteip": remote_ip}`. فراخوانده از `claim.py:124` و `contact.py:79`.

**کمترین تغییر:** `remoteip` پارامتر **اختیاری** Turnstile است. حذفش یک خط است.

**چه می‌شکند:** دقت امتیازدهی Turnstile کمی افت می‌کند (بدون IP نمی‌تواند توکن را به
مبدأ گره بزند، پس بازپخش توکن از یک IP دیگر سخت‌تر تشخیص داده می‌شود). با توجه به اینکه
محدودسازی نرخ **هم** پشت این دو مسیر هست، معامله‌ی معقولی است.

**ولی توجه:** این تغییر عملاً چیزی را از Cloudflare پنهان نمی‌کند — مورد E زیر.

---

### E — خود Cloudflare

🟢 ساختاری. `CLAUDE.md` می‌گوید رکورد DNS باید **Proxied** باشد و
`web/routes/public/identity.py:69-77` مستقیماً به `CF-Connecting-IP` تکیه می‌کند. یعنی
Cloudflare **در مسیر است و IP هر بازدیدکننده را می‌بیند** — این پیش‌فرض معماری است.

**کمترین تغییر: هیچ.** غیرقابل رفع بدون کنار گذاشتن Cloudflare، که یعنی از دست دادن هم
پنهان‌ماندن IP سرور مبدأ و هم لایه‌ی ضد-DDoS. به بخش ۶ رفت.

---

### F — بکاپ شبانه

🟢 **کاملاً رد زده شد.** `backend/gozar/worker/tasks.py:595-670`:

```
cron(backup_database, hour=3, minute=0)            # worker/main.py:103
  → _pg_dump_argv_env(settings.database_url)       # فقط DATABASE_URL
  → pg_dump --no-owner --no-privileges -w
  → gzip
  → bot.send_document(BACKUP_CHANNEL_ID, …)
```

**پاسخ صریح به سؤال ۳:**

| در بکاپ هست؟ | | دلیل |
|---|---|---|
| دیتابیس GozarX | ✅ بله | `DATABASE_URL` — تنها چیزی که dump می‌شود |
| دیتابیس Remnawave | ❌ **خیر** | استکِ جداست. GozarX فقط `PANEL_BASE_URL` + توکن API دارد (`.env.example:30-31`) — هیچ رشته‌ی اتصال به DB پنل وجود ندارد |
| Redis (خودمان) | ❌ **خیر** | هیچ dump یا کپی Redisای در هیچ تسکی نیست |
| Redis (پنل) | ❌ **خیر** | `REDIS_URL` به Redis خودمان اشاره می‌کند (`.env.example:44`) |
| فایل `.env` | ❌ **خیر** | فقط pg dump فرستاده می‌شود |

**پس تنها داده‌ی IP-محورِ داخل بکاپ، ستون `ip_bucket` است — هش، بدون نمک.**

**آنچه باقی می‌ماند:** dump شامل هر `telegram_id`، هر `panel_username` و هر `ip_bucket`
است و **برای همیشه در یک کانال تلگرام می‌ماند** — هیچ چیزی پیام‌های کانال را پاک نمی‌کند.

**کمترین تغییر:** کانال بکاپ باید خصوصی باشد با حداقل عضو، و یک سیاست دستی «پیام‌های
قدیمی‌تر از N روز را پاک کن». اگر می‌خواهید سخت‌تر: dump را قبل از ارسال با یک کلید
symmetric رمز کنید.

**چه می‌شکند:** بازیابی یک قدم بیشتر می‌شود (رمزگشایی قبل از restore) و کلید باید جایی
خارج از تلگرام نگه‌داری شود.

---

### G / H / I — سه محل ذخیره‌سازی IP در Remnawave

🟢 **ساختار اثبات‌شده از `prisma/schema.prisma`؛** 🟡 **حجم و اینکه اصلاً پر شده‌اند یا نه،
نیازمند بررسی زنده.**

| | جدول · ستون | چه چیزی آن را می‌نویسد | Retention |
|---|---|---|---|
| **G** | `hwid_user_devices.request_ip` (`:342`) | وقتی کلاینت هدرهای HWID می‌فرستد (Happ، v2rayTUN و…) موقع گرفتن subscription — `src/modules/subscription/subscription.service.ts:227,361` | **هیچ.** فقط حذف دستی |
| **H** | `user_subscription_request_history.request_ip` (`:498`) | هر بار گرفتن subscription، مگر `SERVICE_DISABLE_SRH_RECORDS=true` — `src/queue/_users/processors/subscription-requests.processor.ts:78-110` | **۲۴ ردیف آخر هر کاربر** (`cleanupUserRecords(userId, 24)`)، بدون سقف زمانی |
| **I** | `torrent_blocker_reports.report` → `xrayReport.source` (`:619`) | فقط اگر پلاگین torrent-blocker روی نودی فعال باشد | **هیچ.** فقط truncate دستی |

تأیید شد که **تنها cron پاک‌سازی پنل** (`CLEAN_OLD_USAGE_RECORDS`) فقط
`nodes_user_usage_history` را truncate می‌کند — جدولی که اصلاً IP ندارد
(`src/queue/service/service.processor.ts:39-56`). **هیچ retentionای روی این سه جدول نیست.**

**کمترین تغییرها:**

| | تغییر | چه می‌شکند |
|---|---|---|
| **H** | `SERVICE_DISABLE_SRH_RECORDS=true` در `.env` پنل | صفحه‌ی «تاریخچه‌ی درخواست subscription» و آمار «کدام اپ» خالی می‌شود. برای ما بی‌استفاده است — ما این صفحه را نمی‌خوانیم |
| **G** | HWID فقط وقتی فعال است که کاربر `hwidDeviceLimit` داشته باشد. کلاینت `RemnawaveClient.create_trial_user` ما این فیلد را **ست نمی‌کند** (`backend/gozar/remnawave/client.py:110-121`) — پس احتمالاً برای کاربران trial ما خاموش است. **باید شمرده شود** (۵.۲) | اگر روشنش کرده باشید: سقف تعداد دستگاه از کار می‌افتد |
| **I** | اگر پلاگین torrent-blocker روی هیچ نودی فعال نیست، این جدول خالی است. **باید شمرده شود** (۵.۲) | خاموش‌کردنش یعنی بلاک تورنت از کار می‌افتد |

⚠️ **این سه، دیتابیس Remnawave است، نه ما.** اگر پنل را شخص دیگری می‌گرداند، ما فقط
می‌توانیم درخواست بدهیم.

---

### J — استریم‌های صادرات Redis پنل

🟢 پیش‌فرض `EXPORT_TO_STREAM_ENABLED` برابر **`false`** است
(`src/common/config/app-config/config.schema.ts:93`، `booleanString('false')`).
🟡 مقدار زنده باید چک شود — **و خوشبختانه این یکی بدون shell قابل چک است** (۵.۱).

نکته‌ی مهمی که با جست‌وجو تأیید شد: **در کل کد Remnawave هیچ `XREAD`/`XRANGE`/consumer
group وجود ندارد.** پنل این استریم‌ها را فقط **می‌نویسد** — برای مصرف‌کننده‌ی بیرونی طراحی
شده‌اند. پس اگر روشن باشد و ما مصرف‌کننده‌ای نداشته باشیم (نداریم — `REDIS_URL` ما به Redis
خودمان اشاره می‌کند)، **داده‌ی IP+هویت بی‌استفاده انباشته می‌شود**.

سقف‌ها *تنظیم شده‌اند* (نه نامحدود):
- `ioraw:export:node_connections` — `XADD … MINID ~ (now − 1h)` → پنجره‌ی ۱ ساعته
- `ioraw:export:subscription_requests` — `XADD … MAXLEN ~ EXPORT_TO_STREAM_MAXLEN`

**کمترین تغییر:** `EXPORT_TO_STREAM_ENABLED=false`.
**چه می‌شکند:** هیچ — ما مصرف‌کننده‌ای نداریم. (اگر گزارش تله‌متری قبلی روزی پیاده شود،
معماری توصیه‌شده‌ی آن هم عمداً از این استریم استفاده نمی‌کند، دقیقاً به همین دلیل.)

---

### K — لاگ Xray روی نودها

🟢 **مهم‌ترین یافته‌ی این حسابرسی، و کاملاً از کد اثبات شده.**

کانفیگ پیش‌فرضی که پنل seed می‌کند (`prisma/seed/default/xray-config.ts:1-4`):

```ts
export const XRAY_DEFAULT_CONFIG = {
    log: { loglevel: 'info' },      // ← بدون کلید access
    ...
```

و منطق Xray (`Xray-core/infra/conf/log.go:26-36`):

```go
config := &log.Config{
    ErrorLogType:  log.LogType_Console,
    AccessLogType: log.LogType_Console,   // ← پیش‌فرضِ داخلِ Build() روشن است
}
if v.AccessLog == "none" { config.AccessLogType = log.LogType_None }
```

**یعنی: به‌محض اینکه یک بلوک `log` در کانفیگ باشد، access log روشن است** — مگر
`access: "none"` یا `loglevel: "none"` صریحاً نوشته شود.

و — نکته‌ای که راحت اشتباه می‌شود — **access log تابع `loglevel` نیست**
(`Xray-core/app/log/log.go:126-136`):

```go
case *log.AccessMessage:
    if g.accessLogger != nil { g.accessLogger.Handle(Msg) }   // بدون فیلتر severity
case *log.GeneralMessage:
    if g.errorLogger != nil && msg.Severity <= g.config.ErrorLogLevel { … }  // ← فقط این فیلتر می‌شود
```

**پس `loglevel: "warning"` هم access log را خاموش نمی‌کند.** تنها این دو خاموشش می‌کنند:
`access: "none"` یا `loglevel: "none"`. (فقط وقتی *اصلاً* بلوک `log` نباشد،
`DefaultLogConfig()` با `AccessLogType: LogType_None` اعمال می‌شود — یعنی
**افزودن یک بلوک `log` که به نظر می‌رسد لاگ را کم می‌کند، در واقع access log را روشن می‌کند.**)

محتوای هر خط: `from <IP:port> accepted <مقصد> [تگ] email: <شناسه‌ی عددی کاربر پنل>`
(`Xray-core/common/log/access.go:33-58`، `proxy/vless/inbound/inbound.go:601-607`).
آن `email` همان `users.id` پنل است
(`backend/src/modules/nodes/events/add-user-to-node/add-user-to-node.handler.ts:66`).
**پس یک خط لاگ، IP و هویت را کنار هم دارد.**

مقصد و نگهداری (`node/rootfs/etc/s6-overlay/s6-rc.d/`):
```sh
xray/run:      exec 2>&1 ; exec /usr/local/bin/rw-core -config @… -format json
xray-log/run:  exec /command/s6-log -b n0 s10485760 /var/log/xray
```
`s10485760` = چرخش در ۱۰ MB · `n0` = **صفر فایل آرشیو نگه‌دار** → فایل قدیمی بلافاصله حذف
می‌شود. **پس نگهداری = آخرین ≤۱۰ MB خروجی، و نه بیشتر.** روی یک نود شلوغ در سطح `info`
این می‌تواند فقط چند دقیقه باشد. این یک عامل کاهنده‌ی واقعی است — آرشیو نیست، بافر است.

**کمترین تغییر — دو گزینه، هر دو یک‌خطی در پروفایل کانفیگ پنل:**

```jsonc
// گزینه ۱ — access log کاملاً خاموش (تمیزترین)
"log": { "loglevel": "warning", "access": "none" }

// گزینه ۲ — لاگ بماند، آدرس‌ها حذف شوند
"log": { "loglevel": "warning", "maskAddress": "full" }
```

`maskAddress` گزینه‌ی خود Xray است (`Xray-core/app/log/log.go:166-178`):
`"full"` → `/0` (کاملاً پنهان) · `"half"` → `/16` · `"quarter"` → `/8` · یا فرم دلخواه
`"/24+/48"`.

**چه می‌شکند:**
- گزینه ۱: عیب‌یابی «چرا اتصال این کاربر رد شد» روی نود ممکن نیست. `error log` می‌ماند.
- گزینه ۲: خطوط access می‌مانند (پس مقصد و کاربر هنوز دیده می‌شوند) ولی IP رفته. اگر
  `"full"` سنگین بود، `"quarter"` (/8) هم برای هر تشخیص عملیاتی کافی است و IP را
  غیرقابل شناسایی می‌کند.

⚠️ **این تغییر در «پروفایل کانفیگ» پنل Remnawave انجام می‌شود و باعث ری‌استارت Xray روی
نودها می‌شود** — یعنی قطع کوتاه اتصال همه‌ی کاربران آن نود. باید در ساعت کم‌ترافیک انجام شود.

---

## ۳. آنچه پاک است — و ارزش ثبت دارد

این‌ها را گشتم و **چیزی پیدا نشد**:

| بررسی | نتیجه |
|---|---|
| ستون IP در اسکیمای GozarX | ❌ هیچ. تنها ستون IP-محور `ip_bucket` است که هش است |
| هر خط لاگی در بک‌اند GozarX که IP داشته باشد | ❌ هیچ — کل `logger.*` گرفته شد و هیچ‌کدام متغیر IP-محور ندارند |
| لاگ دسترسی uvicorn | ✅ خاموش — `"uvicorn.access": {"level": "WARNING"}` در `config/logging.py` |
| فرمتر لاگ | ✅ فقط `ts/level/logger/msg` — هیچ فیلد شبکه‌ای |
| Sentry / PostHog / Datadog / GA / OpenTelemetry | ❌ **هیچ SDK تله‌متری خارجی در هیچ‌کدام از سه فرانت‌اند و بک‌اند نیست** |
| گیرنده‌ی `/panel-webhook` | ✅ بدنه‌ی خام هیچ‌وقت لاگ نمی‌شود؛ `WebhookUserEvent` با `extra="ignore"` پارس می‌کند، پس حتی اگر پنل رویداد HWID با `requestIp` بفرستد، دور ریخته می‌شود |
| ربات تلگرام | ✅ آپدیت‌ها از سرورهای تلگرام می‌آیند — ربات هیچ‌وقت IP کاربر را نمی‌بیند |

---

## ۴. پیشنهادها به ترتیب اولویت

| اولویت | مورد | تغییر | ریسک شکست |
|---|---|---|---|
| **۱** | **B** | شش نقطه: `client_ip(request)` → `ip_bucket(request, secret)` | ~هیچ. داکسترینگ موجود همین را می‌گوید |
| **۲** | **K** | `"access": "none"` یا `"maskAddress": "full"` در پروفایل کانفیگ | ری‌استارت Xray → قطع کوتاه |
| **۳** | **J** | `EXPORT_TO_STREAM_ENABLED=false` **اگر روشن است** | هیچ — مصرف‌کننده‌ای نداریم |
| **۴** | **H** | `SERVICE_DISABLE_SRH_RECORDS=true` | صفحه‌ی تاریخچه‌ی subscription پنل خالی می‌شود |
| **۵** | **C** | `access_log off;` + `logging:` با `max-size` در compose | عیب‌یابی HTTP سخت‌تر |
| **۶** | **A** | نمک جدا، یا NULL کردن `ip_bucket` دستگاه‌های خفته | سیگنال ضدسوءاستفاده برای دستگاه‌های قدیمی |
| **۷** | **D** | حذف `remoteip` از فراخوان Turnstile | افت جزئی دقت Turnstile |
| **۸** | **F** | کانال بکاپ خصوصی + پاک‌سازی دوره‌ای، یا رمزگذاری dump | بازیابی یک قدم بیشتر |

---

## ۵. بررسی‌های زنده‌ی لازم — همه فقط-خواندنی

هیچ‌کدام چیزی را تغییر نمی‌دهند. مقادیر واقعی را در پاسخ **بازنویسی نکنید** — فقط
«روشن/خاموش» و «تعداد».

### ۵.۱ وضعیت `EXPORT_TO_STREAM_ENABLED` — بدون نیاز به shell سرور پنل

پنل آن را در یک endpoint می‌دهد (`src/modules/system/system.service.ts:110-145`):

```bash
curl -sS -H "Authorization: Bearer $PANEL_API_TOKEN" \
  "$PANEL_BASE_URL/api/system/configuration" | jq '.response.service, .response.notifications.webhook'
```
دنبال `exportToRedisStream` و `disableSrhRecords` بگردید.

### ۵.۲ حجم سه جدول IP-محور پنل (روی هاست پنل Remnawave)

```bash
docker exec -i <remnawave-db> psql -U <user> -d <db> -c "
  SELECT 'hwid_user_devices'  AS t, count(*) AS rows, count(request_ip) AS with_ip FROM hwid_user_devices
  UNION ALL SELECT 'user_sub_request_history', count(*), count(request_ip) FROM user_subscription_request_history
  UNION ALL SELECT 'torrent_blocker_reports', count(*), count(*) FROM torrent_blocker_reports;"
```
فقط ستون‌های شمارش برگردانده می‌شود — هیچ محتوایی.

### ۵.۳ طول استریم‌ها (روی Redis پنل — فقط اگر ۵.۱ گفت روشن است)

```bash
docker exec -i <remnawave-redis> redis-cli XLEN ioraw:export:node_connections
docker exec -i <remnawave-redis> redis-cli XLEN ioraw:export:subscription_requests
```
`XLEN` فقط طول می‌دهد، محتوا نه. **`XRANGE` نزنید** — محتوا IP خام است.

### ۵.۴ قالب لاگ nginx + حجم لاگ داکر (روی سرور GozarX)

```bash
docker compose exec nginx grep -n "log_format\|access_log" /etc/nginx/nginx.conf
sudo du -sh /var/lib/docker/containers/*/*-json.log | sort -h | tail -5
cat /etc/docker/daemon.json 2>/dev/null || echo "no daemon.json (defaults = unbounded)"
```
اولی می‌گوید `$http_x_forwarded_for` در قالب هست یا نه — **این تعیین می‌کند مورد C کم‌خطر
است یا جدی**.

### ۵.۵ سطح لاگ زنده‌ی Xray (پروفایل کانفیگ در پنل)

در پنل Remnawave → Config Profiles → پروفایل فعال → بلوک `log` را ببینید.
یا روی یک نود:
```bash
docker exec -i <node> sh -c 'ls -l /var/log/xray/ && wc -c /var/log/xray/current'
```
**فایل را `cat`/`tail` نکنید** — همان چیزی است که دنبالش هستیم. فقط اندازه.
اگر `current` دارد رشد می‌کند و بلوک `log` کلید `access: "none"` ندارد، مورد K فعال است.

### ۵.۶ کلیدهای rate-limit در Redis خودمان

```bash
docker compose exec redis redis-cli --scan --pattern 'site:rl:*_ip:*' | wc -l
docker compose exec redis redis-cli --scan --pattern 'site:rl:*' | wc -l
```
فقط `| wc -l` — **خود کلیدها را چاپ نکنید**، چون نامشان IP است.

---

## ۶. ریسک باقی‌مانده

چیزهایی که با هیچ تغییری در این مخزن حذف نمی‌شوند:

### ۶.۱ Cloudflare در مسیر است — ساختاری
هر بازدیدکننده‌ی سایت IPش را به Cloudflare نشان می‌دهد، قبل از اینکه بسته به سرور ما برسد.
معماری *به این وابسته است*: `client_ip()` عمداً `CF-Connecting-IP` را ترجیح می‌دهد چون تنها
هدری است که کاربر نمی‌تواند جعل کند. کنار گذاشتن Cloudflare یعنی از دست دادن هم پنهان‌ماندن
IP مبدأ سرور و هم لایه‌ی ضد-DDoS. **این یک معامله است، نه یک اشکال — ولی باید آگاهانه باشد.**

### ۶.۲ نود، IP را می‌بیند — قابل حذف نیست
یک پروکسی باید بداند بسته را به کجا برگرداند. حتی با `access: "none"` و
`maskAddress: "full"`، Xray در لحظه IP را در حافظه دارد و پشته‌ی TCP سیستم‌عامل هم.
**کاری که می‌شود کرد فقط این است که ننویسدش.**

### ۶.۳ تناقض ذاتی `ip_bucket`
یک سیگنال ضدسوءاستفاده که «آیا این دستگاه‌ها از یک شبکه‌اند» را جواب بدهد، **باید** چیزی
درباره‌ی شبکه نگه دارد. طراحی فعلی (هش نمکی‌شده‌ی /24) تقریباً بهترین حالت است: خودش IP
نیست، ولی همان کار را می‌کند. **تنها چیزی که آن را از IP جدا نگه می‌دارد نمک است** — یعنی
`SITE_COOKIE_SECRET`. اگر `.env` لو برود، هر `ip_bucket` در چند ثانیه به /24 برمی‌گردد.
پس محافظت از `.env` مستقیماً *همان* محافظت از IPهاست، و باید این‌طور فهمیده شود.

### ۶.۴ بکاپ‌های تلگرام برگشت‌ناپذیرند
هر dump شبانه که تا امروز فرستاده شده در کانال است و **پاک نمی‌شود مگر دستی**. هر تغییری
که امروز اعمال شود فقط روی بکاپ‌های *آینده* اثر دارد. بکاپ‌های موجود همچنان
`ip_bucket` هر دستگاهِ آن‌روز را دارند. **این را برایتان پاک نکردم — بند ۲ صریح بود — ولی
پاک‌سازی گذشته یک تصمیم جداست که باید بگیرید.**

### ۶.۵ دیتابیس پنل شاید مال ما نباشد
موارد G/H/I/J در استک Remnawave‌اند. اگر پنل و نودها را شخص دیگری می‌گرداند، ما نه
`.env`ش را می‌بینیم نه می‌توانیم عوضش کنیم — **فقط می‌توانیم درخواست بدهیم.** و در آن حالت
مورد K (لاگ Xray) هم خارج از دسترس ماست.

### ۶.۶ چیزی که این حسابرسی نمی‌تواند بگوید
من دیتابیس زنده را ندیدم. **نمی‌توانم بگویم آیا این جداول واقعاً پر شده‌اند.** بخش ۵ دستور
شمارش می‌دهد. تا وقتی آن اعداد نیامده‌اند، همه‌ی موارد G/H/I «مسیر موجود» است، نه
«نشت تأییدشده» — و من تفاوت این دو را عمداً حفظ کرده‌ام.

---

## ۷. ضمیمه — نقشه‌ی مراجع

| موضوع | فایل |
|---|---|
| `client_ip` / `_coarse_ip` / `ip_bucket` | `backend/gozar/web/routes/public/identity.py:59-108` |
| نوشتن `ip_bucket` (فقط موقع ساخت دستگاه) | `backend/gozar/web/routes/public/identity.py:182-190` |
| مدل `SiteDevice.ip_bucket` | `backend/gozar/db/models/site_device.py:52` |
| ساخت کلید rate-limit (IP خام) | `backend/gozar/cache/redis.py:94-97` |
| شش فراخوان با IP خام | `claim.py:116` · `contact.py:71` · `push.py:77` · `transfer.py:68,91` · `device.py:48` |
| Turnstile با `remoteip` | `backend/gozar/web/routes/public/security.py:23-41` |
| تسک بکاپ | `backend/gozar/worker/tasks.py:588-670` · زمان‌بندی `worker/main.py:103` |
| کانفیگ لاگ (uvicorn.access خاموش) | `backend/gozar/config/logging.py` |
| گیرنده‌ی webhook پنل (بدنه لاگ نمی‌شود) | `backend/gozar/web/routes/panel.py:56-70` |
| nginx (بدون `access_log`) | `nginx/nginx.conf` · `install.sh:470-590` |
| بدون `logging:` در compose | `docker-compose.yml` |
| symlink لاگ در ایمیج nginx | `nginx/docker-nginx` → `stable/debian/Dockerfile:133` |
| جداول IP-محور پنل | `remnawave/backend` → `prisma/schema.prisma:342,498,619` |
| نبود retention (فقط usage-history پاک می‌شود) | `remnawave/backend` → `src/queue/service/service.processor.ts:39-56` |
| سقف ۲۴ ردیف در تاریخچه‌ی subscription | `…/user-subscription-request-history.repository.ts:213-228` |
| پرچم `SERVICE_DISABLE_SRH_RECORDS` | `remnawave/backend` → `src/common/config/app-config/config.schema.ts:92` |
| پرچم `EXPORT_TO_STREAM_ENABLED` (پیش‌فرض false) | همان‌جا `:93` |
| endpoint پیکربندی (چک بدون shell) | `remnawave/backend` → `src/modules/system/system.service.ts:110-145` |
| کانفیگ Xray پیش‌فرض seed‌شده (`loglevel: info`) | `remnawave/backend` → `prisma/seed/default/xray-config.ts:1-4` |
| پیش‌فرضِ روشنِ access log | `XTLS/Xray-core` → `infra/conf/log.go:26-36` |
| access log فیلترِ severity ندارد | `XTLS/Xray-core` → `app/log/log.go:126-136` |
| معناشناسی `maskAddress` | `XTLS/Xray-core` → `app/log/log.go:166-178` |
| قالب خط access (IP + email) | `XTLS/Xray-core` → `common/log/access.go:33-58` |
| چرخش ۱۰MB / بدون آرشیو | `remnawave/node` → `rootfs/etc/s6-overlay/s6-rc.d/xray-log/run` |
