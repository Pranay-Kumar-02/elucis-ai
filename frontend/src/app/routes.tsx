import { Navigate, type RouteObject } from "react-router";

import { AppShell, type RouteHandle } from "@/components/layout/AppShell";
import { NotFoundPage } from "@/components/layout/NotFoundPage";
import { RouteError } from "@/components/layout/RouteError";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { SignInPage } from "@/features/auth/SignInPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { ImportsPage } from "@/features/sources/ImportsPage";
import { SystemStatusPage } from "@/features/system/SystemStatusPage";
import { MembersPage } from "@/features/workspaces/MembersPage";
import { WorkspaceSettingsPage } from "@/features/workspaces/WorkspaceSettingsPage";
import { WorkspacesPage } from "@/features/workspaces/WorkspacesPage";

const handle = (title: string): RouteHandle => ({ title });

/** Route table. Sections from D12 are added here as each one is built end to end. */
export const routes: RouteObject[] = [
  // Public: everything else needs a session (FR-AUTH-02).
  { path: "/sign-in", element: <SignInPage />, errorElement: <RouteError /> },
  { path: "/register", element: <RegisterPage />, errorElement: <RouteError /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    errorElement: <RouteError />,
    children: [
      { index: true, element: <DashboardPage />, handle: handle("Dashboard") },
      { path: "imports", element: <ImportsPage />, handle: handle("Imports") },
      { path: "workspaces", element: <WorkspacesPage />, handle: handle("Workspaces") },
      { path: "settings/general", element: <WorkspaceSettingsPage />, handle: handle("Settings") },
      { path: "settings/members", element: <MembersPage />, handle: handle("Members") },
      { path: "settings/system", element: <SystemStatusPage />, handle: handle("System status") },
      { path: "settings", element: <Navigate to="/settings/general" replace /> },
      // Earlier development paths.
      { path: "system", element: <Navigate to="/settings/system" replace /> },
      { path: "dev/file-preview", element: <Navigate to="/imports" replace /> },
      { path: "*", element: <NotFoundPage />, handle: handle("Not found") },
    ],
  },
];
