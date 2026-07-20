import { IntakeWorkspace } from "../../../components/intake-workspace";

export const dynamic = "force-dynamic";

export default async function ProjectPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <IntakeWorkspace projectId={projectId} />;
}
