
const API_URL = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, "");

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  if (!API_URL) {
    throw new Error("EXPO_PUBLIC_API_URL is not configured");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    // Domain errors send detail.message; validation errors (422) send a list.
    const data: any = await response.json().catch(() => null);
    const detail = data?.detail;
    const message =
      typeof detail?.message === "string" ? detail.message
      : Array.isArray(detail) && typeof detail[0]?.msg === "string" ? detail[0].msg
      : null;
    throw new Error(message ?? `API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}
