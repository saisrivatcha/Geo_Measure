import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";

import { feature, fileRecord, measurementsPage } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { API, errorEnvelope, server } from "@/test/server";

const FILE = fileRecord();
const ROUTE = `/files/${FILE.id}/measurements`;

function pageOf(page: number, pageSize: number, total: number) {
  const start = (page - 1) * pageSize;
  const count = Math.max(0, Math.min(pageSize, total - start));
  return measurementsPage(
    Array.from({ length: count }, (_, i) => feature({ feature_index: start + i })),
    { page, pageSize, total },
  );
}

describe("Measurements page", () => {
  it("shows a skeleton, then the summary and the first page", async () => {
    server.use(
      http.get(`${API}/api/files/:id/`, () => HttpResponse.json(FILE)),
      http.get(`${API}/api/files/:id/measurements/`, async () => {
        await delay(50);
        return HttpResponse.json(pageOf(1, 50, 120));
      }),
    );
    renderApp(ROUTE);

    expect(await screen.findByRole("status", { name: "Loading Feature measurements" })).toBeInTheDocument();
    const summary = await screen.findByLabelText("Measurement summary");
    expect(await within(summary).findByText("120")).toBeInTheDocument();
    expect(within(summary).getByText("100")).toBeInTheDocument(); // measured
    expect(screen.getAllByRole("row", { name: /^Feature \d+,/ })).toHaveLength(50);
    expect(screen.getByText("1–50 of 120 features")).toBeInTheDocument();
  });

  it("pages through results using the API's pagination", async () => {
    const requested: string[] = [];
    server.use(
      http.get(`${API}/api/files/:id/`, () => HttpResponse.json(FILE)),
      http.get(`${API}/api/files/:id/measurements/`, ({ request }) => {
        const url = new URL(request.url);
        requested.push(`${url.searchParams.get("page")}/${url.searchParams.get("page_size")}`);
        return HttpResponse.json(
          pageOf(Number(url.searchParams.get("page")), Number(url.searchParams.get("page_size")), 120),
        );
      }),
    );
    const user = userEvent.setup();
    renderApp(ROUTE);
    await screen.findByRole("row", { name: /^Feature 0,/ });

    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByRole("row", { name: /^Feature 50,/ })).toBeInTheDocument();
    expect(screen.getByText("51–100 of 120 features")).toBeInTheDocument();

    await user.selectOptions(screen.getByRole("combobox", { name: "Rows per page" }), "100");
    await waitFor(() => expect(requested.at(-1)).toBe("1/100"));
    expect(requested).toContain("2/50");
  });

  it("opens a feature in a side panel", async () => {
    server.use(
      http.get(`${API}/api/files/:id/`, () => HttpResponse.json(FILE)),
      http.get(`${API}/api/files/:id/measurements/`, () => HttpResponse.json(pageOf(1, 50, 3))),
      http.get(`${API}/api/files/:id/features/:index`, () =>
        HttpResponse.json({
          ...feature({ feature_index: 1 }),
          display_geometry: { type: "Point", coordinates: [78.48, 17.38] },
          geometry: { type: "Point", coordinates: [78.48, 17.38] },
        }),
      ),
    );
    const user = userEvent.setup();
    renderApp(ROUTE);
    await user.click(await screen.findByRole("row", { name: /^Feature 1,/ }));

    const panel = await screen.findByRole("dialog", { name: "Feature 1" });
    expect(within(panel).getByText("15,234.83 m²")).toBeInTheDocument();
    expect(within(panel).getByText("15,234.82731")).toHaveAttribute("value", "15234.82731");
    expect(within(panel).getByText("Plot 1")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("explains why a failed file has no measurements", async () => {
    server.use(
      http.get(`${API}/api/files/:id/`, () => HttpResponse.json(fileRecord({ status: "FAILED" }))),
      http.get(`${API}/api/files/:id/measurements/`, () =>
        HttpResponse.json(
          errorEnvelope("FILE_NOT_PROCESSED", "The file is FAILED; results are only available once COMPLETED.", {
            status: "FAILED",
            processing_error: "The uploaded file is not a valid ZIP archive.",
          }),
          { status: 409 },
        ),
      ),
    );
    renderApp(ROUTE);
    expect(await screen.findByRole("heading", { name: "No measurements for this file." })).toBeInTheDocument();
    expect(screen.getByText("Processing failed: The uploaded file is not a valid ZIP archive.")).toBeInTheDocument();
  });

  it("offers the first page when the URL points past the end", async () => {
    server.use(
      http.get(`${API}/api/files/:id/`, () => HttpResponse.json(FILE)),
      http.get(`${API}/api/files/:id/measurements/`, ({ request }) => {
        const page = Number(new URL(request.url).searchParams.get("page"));
        return HttpResponse.json(pageOf(page, 50, 3));
      }),
    );
    const user = userEvent.setup();
    renderApp(`${ROUTE}?page=9`);
    expect(await screen.findByRole("heading", { name: "This page is empty." })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Go to first page" }));
    expect(await screen.findByRole("row", { name: /^Feature 0,/ })).toBeInTheDocument();
  });
});
