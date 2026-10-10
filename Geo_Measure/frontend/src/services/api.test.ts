import { http, HttpResponse } from "msw";

import { API, errorEnvelope, server } from "@/test/server";

import { ApiError, getFile, getFiles, toApiError } from "./api";

describe("api client", () => {
  it("sends list filters as query parameters", async () => {
    let url: URL | null = null;
    server.use(
      http.get(`${API}/api/files/`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ items: [], page: 2, page_size: 50, total: 0, total_pages: 0 });
      }),
    );
    await getFiles({ page: 2, page_size: 50, file_type: "KML", q: "parcel", status: undefined });
    expect(url!.searchParams.get("page")).toBe("2");
    expect(url!.searchParams.get("file_type")).toBe("KML");
    expect(url!.searchParams.get("q")).toBe("parcel");
    expect(url!.searchParams.has("status")).toBe(false);
  });

  it("turns the error envelope into an ApiError", async () => {
    server.use(
      http.get(`${API}/api/files/:id/`, () =>
        HttpResponse.json(errorEnvelope("FILE_NOT_FOUND", "File not found.", { file_id: "x" }), { status: 404 }),
      ),
    );
    const error = await getFile("x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: "FILE_NOT_FOUND", message: "File not found." });
    expect((error as ApiError).isNotFound).toBe(true);
  });

  it("reports network failures as NETWORK_ERROR", async () => {
    server.use(http.get(`${API}/api/files/:id/`, () => HttpResponse.error()));
    const error = (await getFile("x").catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe("NETWORK_ERROR");
    expect(error.isNetworkError).toBe(true);
  });

  it("handles responses that are not envelopes", () => {
    expect(toApiError(502, "<html>Bad gateway</html>")).toMatchObject({ status: 502, code: "HTTP_ERROR" });
  });
});
