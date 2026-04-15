const BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const config = {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  };

  const res = await fetch(`${BASE_URL}${endpoint}`, config);

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    const detail =
      errorBody.detail ?? errorBody.message ?? JSON.stringify(errorBody);
    throw new Error(`HTTP ${res.status} ${res.url}: ${detail}`);
  }

  return res.json();
}
