import { Navigate, type RouteObject } from "react-router";

import { AppShell, type RouteHandle } from "@/components/layout/AppShell";
import { NotFoundPage } from "@/components/layout/NotFoundPage";
import { RouteError } from "@/components/layout/RouteError";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { ImportsPage } from "@/features/sources/ImportsPage";
import { SystemStatusPage } from "@/features/system/SystemStatusPage";

const handle = (title: string): RouteHandle => ({ title });

/** Route table. Sections from D12 are added here as each one is built end to end. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <DashboardPage />, handle: handle("Dashboard") },
      { path: "imports", element: <ImportsPage />, handle: handle("Imports") },
      { path: "settings/system", element: <SystemStatusPage />, handle: handle("System status") },
      { path: "settings", element: <Navigate to="/settings/system" replace /> },
      // Earlier development paths.
      { path: "system", element: <Navigate to="/settings/system" replace /> },
      { path: "dev/file-preview", element: <Navigate to="/imports" replace /> },
      { path: "*", element: <NotFoundPage />, handle: handle("Not found") },
    ],
  },
];
