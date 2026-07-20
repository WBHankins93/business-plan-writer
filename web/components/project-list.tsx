"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { authenticatedFetch, SessionExpiredError } from "../lib/api";
import { createClient } from "../lib/supabase/client";

type ProjectSummary = {
  id: string;
  title: string;
  current_step: number;
  updated_at: string;
};

export function ProjectList() {
  const router = useRouter();
  const supabase = useMemo(() => createClient(), []);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const expire = () => {
    router.replace("/login?next=/projects");
    router.refresh();
  };

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [{ data: userData }, response] = await Promise.all([
        supabase.auth.getUser(),
        authenticatedFetch(supabase, "/projects"),
      ]);
      if (!response.ok) throw new Error("Your projects could not be loaded. Try again.");
      setEmail(userData.user?.email || "Signed in");
      setProjects(await response.json());
    } catch (caught) {
      if (caught instanceof SessionExpiredError) return expire();
      setError(caught instanceof Error ? caught.message : "Your projects could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const createProject = async () => {
    setCreating(true);
    setError("");
    try {
      const response = await authenticatedFetch(supabase, "/projects", { method: "POST" });
      if (!response.ok) throw new Error("A new intake could not be started. Try again.");
      const project = await response.json() as ProjectSummary;
      router.push(`/projects/${project.id}`);
    } catch (caught) {
      if (caught instanceof SessionExpiredError) return expire();
      setError(caught instanceof Error ? caught.message : "A new intake could not be started.");
      setCreating(false);
    }
  };

  return (
    <main className="projectsShell">
      <header className="accountHeader">
        <div><p className="eyebrow">Private beta</p><h1>Your business plans</h1></div>
        <div className="accountState"><span>{email}</span><form action="/auth/signout" method="post"><button className="secondary" type="submit">Log out</button></form></div>
      </header>
      {error && <div className="errorSummary" role="alert">{error} <button type="button" onClick={load}>Retry</button></div>}
      <section className="projectsCard">
        <div className="projectsHeading"><div><h2>Saved plans</h2><p>Open a plan to continue your intake or review its draft.</p></div><button type="button" onClick={createProject} disabled={creating}>{creating ? "Starting…" : "Start new plan"}</button></div>
        {loading ? <p className="emptyState">Loading saved plans…</p> : projects.length === 0 ? (
          <div className="emptyState"><h3>No saved plans yet</h3><p>Start a plan and your intake answers will save automatically.</p></div>
        ) : (
          <ul className="projectGrid">
            {projects.map((project) => (
              <li key={project.id}><Link href={`/projects/${project.id}`}><strong>{project.title}</strong><span>Step {project.current_step + 1} of 5</span><small>Saved {new Date(project.updated_at).toLocaleString()}</small></Link></li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
