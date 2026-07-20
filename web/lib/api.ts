import type { SupabaseClient } from "@supabase/supabase-js";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class SessionExpiredError extends Error {}

export async function authenticatedFetch(
  supabase: SupabaseClient,
  path: string,
  init: RequestInit = {}
) {
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session?.access_token) {
    throw new SessionExpiredError("Your session has expired. Sign in again.");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${data.session.access_token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (response.status === 401) {
    await supabase.auth.signOut({ scope: "local" });
    throw new SessionExpiredError("Your session has expired. Sign in again.");
  }
  return response;
}
