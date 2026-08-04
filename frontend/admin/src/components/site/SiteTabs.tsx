import {
  BarChart3,
  BellRing,
  FileText,
  Gauge,
  HelpCircle,
  Inbox,
  MonitorSmartphone,
  Settings2,
  Type,
  Wrench,
} from "lucide-react";

import { NavTabs, type TabItem } from "@/components/ui/Tabs";
import { useI18n, type MessageKey } from "@/i18n";

// Sub-navigation for the "Website" admin section (keeps the sidebar to one entry).
//
// The setup wizard used to be missing from this list AND rendered no tab bar of its own, so opening
// it dropped you out of the section with no way back except one inline link on one page.
const TABS: { to: string; key: MessageKey; icon: TabItem["icon"] }[] = [
  { to: "/site", key: "site.tab.overview", icon: Gauge },
  { to: "/site/settings", key: "site.tab.settings", icon: Settings2 },
  { to: "/site/devices", key: "site.tab.devices", icon: MonitorSmartphone },
  { to: "/site/content", key: "site.tab.content", icon: Type },
  { to: "/site/pages", key: "site.tab.pages", icon: FileText },
  { to: "/site/faq", key: "site.tab.faq", icon: HelpCircle },
  { to: "/site/inbox", key: "site.tab.inbox", icon: Inbox },
  { to: "/site/push", key: "site.tab.push", icon: BellRing },
  { to: "/site/stats", key: "site.tab.stats", icon: BarChart3 },
  { to: "/site/setup", key: "site.tab.setup", icon: Wrench },
];

export function SiteTabs({ unreadMessages }: { unreadMessages?: number }) {
  const { t } = useI18n();
  const items: TabItem[] = TABS.map(({ to, key, icon }) => ({
    to,
    icon,
    label: t(key),
    count: to === "/site/inbox" ? unreadMessages : undefined,
  }));
  return <NavTabs items={items} />;
}
