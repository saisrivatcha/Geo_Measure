import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";

import { processingResult } from "@/test/fixtures";
import { renderApp } from "@/test/render";
import { API, errorEnvelope, server } from "@/test/server";

function kmlFile(name = "survey.kml", content = "<kml/>"): File {
  return new File([content], name, { type: "application/vnd.google-earth.kml+xml" });
}

async function selectFile(user: ReturnType<typeof userEvent.setup>, file: File) {
  await user.upload(screen.getByLabelText("Dataset file"), file);
}

describe("Upload page", () => {
  it("shows the size limit from the API and selects without uploading", async () => {
    let uploads = 0;
    server.use(http.post(`${API}/api/files/`, () => (uploads++, HttpResponse.json({}))));
    const user = userEvent.setup();
    renderApp("/files/upload");

    expect(await screen.findByText("Up to 50 MB")).toBeInTheDocument();
    await selectFile(user, kmlFile());

    expect(screen.getByText("survey.kml")).toBeInTheDocument();
    expect(screen.getByText("KML document, 6 B")).toBeInTheDocument();
    expect(uploads).toBe(0); // nothing is sent until the user asks

    await user.click(screen.getByRole("button", { name: "Remove survey.kml" }));
    expect(screen.getByText("Drag and drop your file here")).toBeInTheDocument();
  });

  it("uploads on request, shows processing, then the result", async () => {
    let received: File | null = null;
    server.use(
      http.post(`${API}/api/files/`, async ({ request }) => {
        received = (await request.formData()).get("file") as File;
        await delay(150);
        return HttpResponse.json(processingResult({ filename: "survey.kml" }), { status: 201 });
      }),
      http.get(`${API}/api/files/:id/geojson`, () =>
        HttpResponse.json({ type: "FeatureCollection", features: [], metadata: {} }),
      ),
    );
    const user = userEvent.setup();
    renderApp("/files/upload");
    await selectFile(user, kmlFile());
    await user.click(screen.getByRole("button", { name: "Process dataset" }));

    expect(await screen.findByText(/Calculating measurements/)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Dataset processed successfully." })).toBeInTheDocument();
    expect(received!.name).toBe("survey.kml");
    expect(screen.getByText("EPSG:4326 (WGS 84)")).toBeInTheDocument();
    expect(screen.getByText("EPSG:32643 (WGS 84 / UTM zone 43N)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View measurements" })).toHaveAttribute(
      "href",
      "/files/3d3e7d3a-0000-4000-8000-000000000001/measurements",
    );
  });

  it("shows the backend's message when processing fails", async () => {
    server.use(
      http.post(`${API}/api/files/`, () =>
        HttpResponse.json(
          errorEnvelope("MISSING_SHAPEFILE_COMPONENTS", "Shapefile 'parcels.shp' is missing: .dbf.", {
            file_id: "abc",
            missing: [".dbf"],
          }),
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderApp("/files/upload");
    await selectFile(user, new File(["PK"], "parcels.zip", { type: "application/zip" }));
    await user.click(screen.getByRole("button", { name: "Process dataset" }));

    expect(await screen.findByRole("heading", { name: "Could not process dataset." })).toBeInTheDocument();
    expect(screen.getByText("Shapefile 'parcels.shp' is missing: .dbf.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try another file" }));
    expect(screen.getByText("Drag and drop your file here")).toBeInTheDocument();
  });

  it("rejects unsupported files before uploading", async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderApp("/files/upload");
    await selectFile(user, new File(["x"], "tour.kmz"));
    expect(screen.getByRole("alert")).toHaveTextContent("KMZ files are not supported");
    expect(screen.queryByRole("button", { name: "Process dataset" })).not.toBeInTheDocument();
  });

  it("lets keyboard users open the file chooser", async () => {
    const user = userEvent.setup();
    renderApp("/files/upload");
    const input = screen.getByLabelText("Dataset file") as HTMLInputElement;
    const click = vi.spyOn(input, "click");

    const chooser = screen.getByRole("button", { name: "Choose file" });
    chooser.focus();
    await user.keyboard("{Enter}");
    expect(click).toHaveBeenCalled();
  });
});
