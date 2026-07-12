import { clsx } from "clsx";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardHeader } from "@/components/ui/Card";
import type { HealthSample } from "@/types/api";

const RANGES: { minutes: number; label: string }[] = [
  { minutes: 60, label: "۱ ساعت" },
  { minutes: 360, label: "۶ ساعت" },
  { minutes: 1440, label: "۲۴ ساعت" },
];

function hhmm(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function HistoryChart({
  samples,
  minutes,
  onMinutesChange,
}: {
  samples: HealthSample[];
  minutes: number;
  onMinutesChange: (m: number) => void;
}) {
  // Keep a failed Telegram latency probe (api_ms === null) as a GAP, not 0 — a 0 ms reading on a
  // latency axis reads as "excellent" and would hide an outage at the chart floor.
  const points = samples.map((s) => ({ t: hhmm(s.ts), api: s.api_ms, pending: s.pending }));
  return (
    <Card>
      <CardHeader
        title="پاسخگویی و تأخیر سرویس"
        action={
          <div className="flex items-center gap-1 rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800">
            {RANGES.map(({ minutes: m, label }) => (
              <button
                key={m}
                onClick={() => onMinutesChange(m)}
                className={clsx(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition",
                  minutes === m
                    ? "bg-white text-brand shadow-sm dark:bg-slate-900"
                    : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        }
      />
      <div className="mb-3 flex items-center gap-4 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-brand" /> تأخیر API تلگرام (ms)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-info" /> آپدیت‌های معلق
        </span>
      </div>
      <div className="h-60" dir="ltr">
        {points.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">
            هنوز داده‌ای ثبت نشده (نمونه‌ها هر دقیقه جمع می‌شوند)
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="g-api" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#7CB000" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#7CB000" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis
                dataKey="t"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                minTickGap={32}
              />
              <YAxis
                yAxisId="api"
                width={36}
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                yAxisId="pending"
                orientation="right"
                width={28}
                allowDecimals={false}
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }}
              />
              <Area
                yAxisId="api"
                type="monotone"
                dataKey="api"
                name="تأخیر (ms)"
                stroke="#7CB000"
                strokeWidth={2}
                fill="url(#g-api)"
                connectNulls={false}
              />
              <Line
                yAxisId="pending"
                type="monotone"
                dataKey="pending"
                name="معلق"
                stroke="#0ea5e9"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
