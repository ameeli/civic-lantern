import { cacheLife, cacheTag } from "next/cache";
import { FEC_DATA_TAG } from "./cacheTags";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

/**
 * GETs a backend endpoint. Responses are kept in the shared remote cache
 * (in-memory `use cache` doesn't survive between serverless instances) until
 * the nightly ingestion revalidates FEC_DATA_TAG, with a daily fallback.
 */
export async function apiFetch<T>(endpoint: string): Promise<T> {
  "use cache: remote";
  cacheTag(FEC_DATA_TAG);
  cacheLife("days");

  const res = await fetch(`${BASE_URL}${endpoint}`, {
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    const detail =
      errorBody.detail ?? errorBody.message ?? JSON.stringify(errorBody);
    throw new Error(`HTTP ${res.status} ${res.url}: ${detail}`);
  }

  return res.json();
}
