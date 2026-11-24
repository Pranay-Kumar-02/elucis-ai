import { Sparkles } from "lucide-react";
import { NavLink, Outlet } from "react-router";

import { navigation } from "@/components/layout/nav";
import { StatusIndicator } from "@/features/system/StatusIndicator";
import { cn } from "@/lib/utils";

export function AppShell() {
  return (
    <div className="flex min-h-svh">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex">
        <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="size-4" aria-hidden />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold">PM Copilot</p>
            <p className="text-xs text-muted-foreground">Group 2 · #Z-5-1</p>
          </div>
        </div>
        <nav aria-label="Main" className="flex-1 space-y-6 p-3">
          {navigation.map((group) => (
            <div key={group.label}>
              <p className="px-2 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {group.label}
              </p>
              <ul className="space-y-0.5">
                {group.items.map(({ to, label, icon: Icon, end }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={end ?? false}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-accent hover:text-accent-foreground",
                          isActive && "bg-accent font-medium text-accent-foreground",
                        )
                      }
                    >
                      <Icon className="size-4" aria-hidden />
                      {label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="border-t border-sidebar-border p-3">
          <StatusIndicator />
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b px-4 md:px-8">
          <p className="text-sm font-semibold md:hidden">PM Copilot</p>
          <p className="hidden text-sm text-muted-foreground md:block">
            AI Product Manager Copilot · development build
          </p>
          <div className="md:hidden">
            <StatusIndicator compact />
          </div>
        </header>
        <main className="flex-1 px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
