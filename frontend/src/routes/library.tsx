import { createFileRoute } from "@tanstack/react-router";
import { PageShell, Placeholder } from "@/components/page-shell";

export const Route = createFileRoute("/library")({
  head: () => ({
    meta: [
      { title: "Manage SDS Library — SDS Manager" },
      { name: "description", content: "Manage SDS Library module for SDS Manager." },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <PageShell>
      <Placeholder title="Manage SDS Library" description="Placeholder content for the Manage SDS Library module." />
    </PageShell>
  );
}
