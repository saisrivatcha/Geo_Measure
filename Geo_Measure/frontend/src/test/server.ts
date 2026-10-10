/** MSW server: the only thing mocked in frontend tests is the HTTP layer. */
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { fileList, healthOk, serviceInfo, stats } from "./fixtures";

export const API = "http://api.test";

export const defaultHandlers = [
  http.get(`${API}/api/health/ready`, () => HttpResponse.json(healthOk)),
  http.get(`${API}/api/meta`, () => HttpResponse.json(serviceInfo)),
  http.get(`${API}/api/stats`, () => HttpResponse.json(stats)),
  http.get(`${API}/api/files/`, () => HttpResponse.json(fileList())),
];

export const server = setupServer(...defaultHandlers);

export function errorEnvelope(code: string, message: string, details: Record<string, unknown> = {}) {
  return { error: { code, message, details } };
}
