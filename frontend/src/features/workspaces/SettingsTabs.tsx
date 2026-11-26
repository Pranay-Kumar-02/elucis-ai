import { NavLink } from "react-router";

import { cn } from "@/lib/utils";

const tabs = [
  { to: "/settings/general", label: "General" },
  { to: "/settings/members", label: "Members" },
  { to: "/settings/system", label: "System status" },
];

/** Settings sections from D12 UI-01: General, Members (and System status). */
export function SettingsTabs() {
  return (
    <nav aria-label="Settings" className="mb-6 flex gap-1 border-b">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            cn(
              "-mb-px border-b-2 px-3 py-2 text-sm transition-colors",
              isActive
                ? "border-primary font-medium text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
