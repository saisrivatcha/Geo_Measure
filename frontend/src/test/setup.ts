import "@testing-library/jest-dom/vitest";

import { Blob as NodeBlob, File as NodeFile } from "node:buffer";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./server";

// jsdom has no matchMedia; the layout uses it to pick sidebar modes.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

// jsdom's File/Blob/FormData cannot be serialised by Node's fetch machinery,
// which MSW's XMLHttpRequest interceptor uses to read request bodies: a
// multipart upload never completes. Use Node's implementations instead (Node's
// FormData is reached through a Response, as it is not exported directly).
const NodeFormData = (
  await new Response("a=b", { headers: { "content-type": "application/x-www-form-urlencoded" } }).formData()
).constructor as typeof FormData;
Object.assign(globalThis, { Blob: NodeBlob, File: NodeFile, FormData: NodeFormData });

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
