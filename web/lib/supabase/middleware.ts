import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const PRIVATE_PATHS = ["/projects"];
const AUTH_PATHS = ["/login", "/register"];

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll(cookiesToSet, headers) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
          Object.entries(headers).forEach(([name, value]) =>
            response.headers.set(name, value)
          );
        },
      },
    }
  );

  const { data, error } = await supabase.auth.getClaims();
  const authenticated = Boolean(data?.claims?.sub) && !error;
  const path = request.nextUrl.pathname;

  if (PRIVATE_PATHS.some((prefix) => path === prefix || path.startsWith(`${prefix}/`)) && !authenticated) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set("next", path);
    return NextResponse.redirect(loginUrl);
  }

  if (AUTH_PATHS.includes(path) && authenticated) {
    const projectsUrl = request.nextUrl.clone();
    projectsUrl.pathname = "/projects";
    projectsUrl.search = "";
    return NextResponse.redirect(projectsUrl);
  }

  return response;
}
