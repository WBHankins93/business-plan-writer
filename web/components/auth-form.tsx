"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { createClient } from "../lib/supabase/client";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const supabase = createClient();
    const result = mode === "login"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password });

    if (result.error) {
      setError(result.error.message);
      setBusy(false);
      return;
    }
    if (mode === "register" && !result.data.session) {
      setNotice("Check your email to confirm your account, then sign in.");
      setBusy(false);
      return;
    }
    const next = searchParams.get("next");
    router.replace(next?.startsWith("/projects") ? next : "/projects");
    router.refresh();
  };

  const isLogin = mode === "login";
  return (
    <main className="authShell">
      <section className="authCard">
        <p className="eyebrow">Private beta</p>
        <h1>{isLogin ? "Welcome back" : "Create your account"}</h1>
        <p>{isLogin ? "Sign in to resume your saved business plan." : "Save your intake and return whenever you are ready."}</p>
        {error && <div className="errorSummary" role="alert">{error}</div>}
        {notice && <p className="notice" role="status">{notice}</p>}
        <form onSubmit={submit} className="authForm">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete={isLogin ? "current-password" : "new-password"} minLength={8} required value={password} onChange={(event) => setPassword(event.target.value)} />
          <button type="submit" disabled={busy}>{busy ? "Please wait…" : isLogin ? "Sign in" : "Create account"}</button>
        </form>
        <p className="authSwitch">
          {isLogin ? "Need an account?" : "Already have an account?"}{" "}
          <Link href={isLogin ? "/register" : "/login"}>{isLogin ? "Create account" : "Sign in"}</Link>
        </p>
        <Link className="demoLink" href="/demo">Explore the fictional demo instead</Link>
      </section>
    </main>
  );
}
