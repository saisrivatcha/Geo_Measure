import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { fileList, fileRecord, geojsonCollection, measurementsPage } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { API, errorEnvelope, server } from "@/test/server";

const FILES = [
  fileRecord(),
  fileRecord({
    id: "3d3e7d3a-0000-4000-8000-000000000002",
    filename: "parcels.zip",
    file_type: "SHAPEFILE",
    feature_count: 240,
    source_crs: "EPSG:32643",
    measurement_crs: "EPSG:32643",
  }),
  fileRecord({
    id: "3d3e7d3a-0000-4000-8000-000000000003",
    filename: "broken.zip",
    file_type: "SHAPEFILE",
    status: "FAILED",
    feature_count: null,
    source_crs: null,
    measurement_crs: null,
    processing_error: "The uploaded file is not a valid ZIP archive.",
  }),
];

describe("Files page", () => {
  it("lists files from the API with type, features, CRS and status", async () => {
    server.use(http.get(`${API}/api/files/`, () => HttpResponse.json(fileList(FILES))));
    renderApp("/files");

    const table = await screen.findByRole("table", { name: "Uploaded files" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(4); // header + 3

    const parcels = within(screen.getByRole("row", { name: "Open parcels.zip" }));
    expect(parcels.getByText("Shapefile")).toBeInTheDocument();
    expect(parcels.getByText("240")).toBeInTheDocument();
    expect(parcels.getAllByText("EPSG:32643")).toHaveLength(2);
    expect(parcels.getByText("Completed")).toBeInTheDocument();
    expect(parcels.getByRole("link", { name: "Measurements for parcels.zip" })).toHaveAttribute(
      "href",
      "/files/3d3e7d3a-0000-4000-8000-000000000002/measurements",
    );

    const broken = within(screen.getByRole("row", { name: "Open broken.zip" }));
    expect(broken.getByText("Failed")).toBeInTheDocument();
    expect(broken.queryByRole("link", { name: /Measurements/ })).not.toBeInTheDocument();
  });

  it("sends filters to the API", async () => {
    const requests: URL[] = [];
    server.use(
      http.get(`${API}/api/files/`, ({ request }) => {
        requests.push(new URL(request.url));
        return HttpResponse.json(fileList(FILES));
      }),
    );
    const user = userEvent.setup();
    renderApp("/files");
    await screen.findByRole("table", { name: "Uploaded files" });

    await user.selectOptions(screen.getByRole("combobox", { name: "Type" }), "SHAPEFILE");
    await user.selectOptions(screen.getByRole("combobox", { name: "Status" }), "FAILED");
    await user.type(screen.getByRole("searchbox", { name: "Search files" }), "broken");

    await waitFor(() => {
      const last = requests.at(-1)!;
      expect(last.searchParams.get("file_type")).toBe("SHAPEFILE");
      expect(last.searchParams.get("status")).toBe("FAILED");
      expect(last.searchParams.get("q")).toBe("broken");
    });
  });

  it("opens a file when its row is activated", async () => {
    server.use(
      http.get(`${API}/api/files/`, () => HttpResponse.json(fileList(FILES))),
      http.get(`${API}/api/files/:id/`, () => HttpResponse.json(FILES[1])),
      http.get(`${API}/api/files/:id/geojson`, () => HttpResponse.json(geojsonCollection())),
      http.get(`${API}/api/files/:id/measurements/`, () => HttpResponse.json(measurementsPage([]))),
    );
    const user = userEvent.setup();
    const { router } = renderApp("/files");
    await user.click(await screen.findByRole("row", { name: "Open parcels.zip" }));
    // The details route is code-split, so navigation completes once it has loaded.
    await waitFor(() => expect(router.state.location.pathname).toBe("/files/3d3e7d3a-0000-4000-8000-000000000002"));
  });

  it("shows an empty state with an upload call to action", async () => {
    server.use(http.get(`${API}/api/files/`, () => HttpResponse.json(fileList([]))));
    renderApp("/files");
    expect(await screen.findByRole("heading", { name: "No geospatial files yet." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload your first dataset" })).toHaveAttribute("href", "/files/upload");
  });

  it("shows an error state and recovers on retry", async () => {
    let fail = true;
    server.use(
      http.get(`${API}/api/files/`, () =>
        fail
          ? HttpResponse.json(errorEnvelope("INTERNAL_ERROR", "An unexpected error occurred."), { status: 500 })
          : HttpResponse.json(fileList(FILES)),
      ),
    );
    const user = userEvent.setup();
    renderApp("/files");

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load files.");
    fail = false;
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("row", { name: "Open survey.kml" })).toBeInTheDocument();
  });
});
