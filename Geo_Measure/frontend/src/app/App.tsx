import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { FilesPage } from "@/pages/FilesPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { UploadPage } from "@/pages/UploadPage";

import { createQueryClient } from "./queryClient";

export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <OverviewPage /> },
      { path: "/files", element: <FilesPage /> },
      { path: "/files/upload", element: <UploadPage /> },
      // Map pages are code-split so Leaflet only loads when a map is shown.
      {
        path: "/files/:id",
        lazy: () => import("@/pages/FileDetailsPage").then((m) => ({ Component: m.FileDetailsPage })),
      },
      {
        path: "/files/:id/measurements",
        lazy: () => import("@/pages/MeasurementsPage").then((m) => ({ Component: m.MeasurementsPage })),
      },
      { path: "/settings", element: <SettingsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export function App({ queryClient }: { queryClient?: QueryClient }) {
  const [client] = useState(() => queryClient ?? createQueryClient());
  const [router] = useState(() => createBrowserRouter(routes));
  return (
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
