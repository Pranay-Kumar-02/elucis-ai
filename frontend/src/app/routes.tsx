import type { RouteObject } from "react-router";

import { AppShell } from "@/components/layout/AppShell";
import { RouteError } from "@/components/layout/RouteError";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { FilePreviewPage } from "@/features/sources/FilePreviewPage";
import { SystemStatusPage } from "@/features/system/SystemStatusPage";
import { NotFoundPage } from "@/components/layout/NotFoundPage";

/** Route table. Feature modules add their routes here as they are built (D12 UI-01..12). */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "system", element: <SystemStatusPage /> },
      { path: "dev/file-preview", element: <FilePreviewPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
