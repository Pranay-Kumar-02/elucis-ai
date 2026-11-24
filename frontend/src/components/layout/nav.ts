import {
  Bot,
  ClipboardCheck,
  FileText,
  Inbox,
  Layers,
  LayoutDashboard,
  ListChecks,
  Map,
  Settings,
  Target,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  icon: LucideIcon;
  /** Route path when the section is available; omitted while it is still being built. */
  to?: string;
  end?: boolean;
}

/**
 * Main navigation, in the order defined by D12 §2. Sections without a route are shown
 * disabled so the product structure is visible without pretending they work.
 */
export const mainNav: NavItem[] = [
  { label: "Dashboard", icon: LayoutDashboard, to: "/", end: true },
  { label: "Imports", icon: Inbox, to: "/imports" },
  { label: "Themes", icon: Layers },
  { label: "Requests", icon: ListChecks },
  { label: "Review", icon: ClipboardCheck },
  { label: "Opportunities", icon: Target },
  { label: "Documents", icon: FileText },
  { label: "Roadmap", icon: Map },
  { label: "Assistant", icon: Bot },
];

export const footerNav: NavItem[] = [{ label: "Settings", icon: Settings, to: "/settings/system" }];

export const UNAVAILABLE_HINT = "Available once feedback analysis is set up";
