import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { routes } from "@/app/App";

export function testQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
}

/** Render a single component inside the providers it needs. */
export function renderWithProviders(ui: ReactElement, { route = "/" }: { route?: string } = {}) {
  const queryClient = testQueryClient();
  const router = createMemoryRouter([{ path: "*", element: ui }], { initialEntries: [route] });
  return { queryClient, ...render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>) };
}

/** Render the real application routes (layout included) at ``route``. */
export function renderApp(route: string) {
  const queryClient = testQueryClient();
  const router = createMemoryRouter(routes, { initialEntries: [route] });
  return { queryClient, router, ...render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>) };
}
