import { createFileRoute } from "@tanstack/react-router";
import { PageShell, Placeholder } from "@/components/page-shell";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — SDS Manager" },
      { name: "description", content: "Overview of Safety Data Sheets, compliance and recent activity." },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <PageShell>
      <Placeholder
        title="Dashboard"
        description="At-a-glance metrics for SDS coverage, compliance and recent uploads."
      />
    </PageShell>
  );
}
