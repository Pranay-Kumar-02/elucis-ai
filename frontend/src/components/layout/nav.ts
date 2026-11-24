import { Activity, FileSearch, LayoutDashboard, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navigation: NavGroup[] = [
  {
    label: "Workspace",
    items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, end: true }],
  },
  {
    label: "Developer",
    items: [
      { to: "/dev/file-preview", label: "File preview", icon: FileSearch },
      { to: "/system", label: "System status", icon: Activity },
    ],
  },
];
