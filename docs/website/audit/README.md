# ممیزی UI/UX سایت عمومی GozarX (مهر ۱۴۰۵ / سپتامبر ۲۰۲۶)

ممیزی کامل رابط و تجربهٔ کاربری `frontend/site` — هم از روی **کد** و هم از روی **رندر واقعی** — که
مرحله‌به‌مرحله ذخیره شده است. کامیت بررسی‌شده: `9b284a1`.

| مرحله | فایل | محتوا |
|---|---|---|
| ۱ | [`01-baseline.md`](01-baseline.md) | اسپک در برابر پیاده‌سازی، تغییرات عمدی مالک، روش |
| ۲ | [`02-code-review.md`](02-code-review.md) | ۶۸ نقد کد (`C-xx`) با فایل:خط و پیشنهاد |
| ۳ | [`mockapi.py`](mockapi.py)، [`audit.py`](audit.py)، [`probe_extra.py`](probe_extra.py) | ابزار رندر: API ساختگی + ۹۱ تصویر + پروب‌ها |
| ۴ | [`03-visual-review.md`](03-visual-review.md)، [`04-probes.md`](04-probes.md)، [`shots/`](shots/) | سنجش نقدها روی تصویر، ۱۴ یافتهٔ بصری تازه (`V-xx`)، اندازه‌گیری‌ها، ۲۴ تصویر شاهد |
| ۵ | [`05-fix-plan.md`](05-fix-plan.md)، [`report.html`](report.html) | گزارش نهایی، تصمیم‌های مالک، پلن ۶ فازی با معیار پذیرش |
| A | [`06-phase-a.md`](06-phase-a.md)، [`shots/phase-a/`](shots/phase-a/) | اجرای فاز A: سنجش قبل/بعد، انحراف‌ها، ۹ تصویر شاهد |
| B | [`07-phase-b.md`](07-phase-b.md)، [`accept_b.py`](accept_b.py)، [`shots/phase-b/`](shots/phase-b/) | اجرای فاز B: پذیرش خودکار در زمان واقعی (۱۵ بررسی)، شاهدها |
| C | [`08-phase-c.md`](08-phase-c.md)، [`accept_c.py`](accept_c.py)، [`shots/phase-c/`](shots/phase-c/) | اجرای فاز C: دکمه در صفحهٔ اول موبایل، مسیرهای ورود به ویجت، پذیرش خودکار (۳۶ بررسی)، شاهدها |

**خلاصه:** پایهٔ بصری، واکنش‌گرایی (۰ سرریز) و پایداری چیدمان (CLS≈۰) خوب است؛ ضعف‌ها در حالت‌های
غیرخوش ویجت (اسکلتون نامرئی، تایمر یخ‌زده، خطای عمومی، revive شکسته)، تبدیل روی موبایل (دکمه زیر
فولد، ویجت دیر در لندینگ)، صداقت متن (عدد ثابت کاربران، «۲۴ ساعت»، «حساب کاربری»)، دسترس‌پذیری
(مودال/هدف لمسی) و چند باگ موضعی RTL است. جزئیات و ترتیب اصلاح در `05-fix-plan.md`.

## تکرار ممیزی

```bash
cd frontend/site && npm ci && npm run build
python3 docs/website/audit/mockapi.py &
BACKEND_ORIGIN=http://127.0.0.1:8000 npx next start -p 3100 &
pip install playwright pillow            # Chromium از قبل روی ماشین هست
python3 docs/website/audit/audit.py /tmp/shots [--only home-]
python3 docs/website/audit/probe_extra.py /tmp/shots
python3 docs/website/audit/accept_b.py /tmp/shots     # رفتار جریان دریافت در طول زمان (~۲ دقیقه)
python3 docs/website/audit/accept_c.py /tmp/shots     # فولد موبایل و مسیرهای ورود به ویجت (~۲ دقیقه)
```

`mockapi.py` حالت‌ها را با کوکی انتخاب می‌کند (`mock_state`، `mock_claim`، `mock_locs`، `mock_delay`، `mock_refs`)
— جدول کامل در docstring همان فایل. دو عددی که صفحهٔ اول **سمت سرور** می‌خواند از کوکی نمی‌آیند و با
متغیر محیطی تنظیم می‌شوند: `MOCK_TRIAL_HOURS` (پیش‌فرض ۲۴) و `MOCK_DELIVERED` (پیش‌فرض ۴۸۲۱۳؛ زیر ۱۰۰۰ چیپ
پنهان می‌شود).
