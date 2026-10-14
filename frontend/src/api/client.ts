import "server-only"; // fails the build if a Client Component imports this (and the key)
import { cacheLife, cacheTag } from "next/cache";
import { FEC_DATA_TAG } from "./cacheTags";

// Server-only settings: no NEXT_PUBLIC_ prefix, so Next never inlines them into browser code.
function requiredEnv(name: "API_URL" | "BACKEND_API_KEY") {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

/*
Responses are kept in the shared remote cache until the nightly ingestion revalidates 
FEC_DATA_TAG, with a daily fallback.
 */
export async function apiFetch<T>(endpoint: string): Promise<T> {
  "use cache: remote";
  cacheTag(FEC_DATA_TAG);
  cacheLife("days");

  const res = await fetch(`${requiredEnv("API_URL")}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${requiredEnv("BACKEND_API_KEY")}`,
    },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    const detail =
      errorBody.detail ?? errorBody.message ?? JSON.stringify(errorBody);
    throw new Error(`HTTP ${res.status} ${res.url}: ${detail}`);
  }

  return res.json();
}
