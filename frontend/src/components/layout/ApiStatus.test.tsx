import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { renderWithProviders } from "@/test/render";
import { API, errorEnvelope, server } from "@/test/server";

import { ApiStatus } from "./ApiStatus";

describe("API health indicator", () => {
  it("reports connected only after the readiness check succeeds", async () => {
    renderWithProviders(<ApiStatus />);
    expect(screen.getByText("Checking API")).toBeInTheDocument();
    expect(await screen.findByText("API connected")).toBeInTheDocument();
  });

  it("reports a degraded API when the database is down", async () => {
    server.use(
      http.get(`${API}/api/health/ready`, () =>
        HttpResponse.json(errorEnvelope("DATABASE_UNAVAILABLE", "The database is not reachable."), { status: 503 }),
      ),
    );
    renderWithProviders(<ApiStatus />);
    expect(await screen.findByText("Database unavailable")).toBeInTheDocument();
  });

  it("reports an unavailable API when the request fails", async () => {
    server.use(http.get(`${API}/api/health/ready`, () => HttpResponse.error()));
    renderWithProviders(<ApiStatus />);
    expect(await screen.findByText("API unavailable")).toBeInTheDocument();
  });
});
