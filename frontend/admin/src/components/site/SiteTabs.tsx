import { BarChart3, BellRing, FileText, Inbox, Settings2, Wrench } from "lucide-react";

import { NavTabs, type TabItem } from "@/components/ui/Tabs";

// Sub-navigation for the "Website" admin section (keeps the sidebar to one entry).
//
// The setup wizard used to be missing from this list AND rendered no tab bar of its own, so opening
// it dropped you out of the section with no way back except one inline link on one page.
const TABS: TabItem[] = [
  { to: "/site/settings", label: "تنظیمات", icon: Settings2 },
  { to: "/site/pages", label: "صفحه‌ها", icon: FileText },
  { to: "/site/inbox", label: "پیام‌ها", icon: Inbox },
  { to: "/site/push", label: "اعلان‌ها", icon: BellRing },
  { to: "/site/stats", label: "آمار", icon: BarChart3 },
  { to: "/site/setup", label: "راه‌اندازی", icon: Wrench },
];

export function SiteTabs({ unreadMessages }: { unreadMessages?: number }) {
  const items = TABS.map((t) => (t.to === "/site/inbox" ? { ...t, count: unreadMessages } : t));
  return <NavTabs items={items} />;
}
