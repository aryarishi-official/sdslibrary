import { createFileRoute } from "@tanstack/react-router";
import { PageShell, Placeholder } from "@/components/page-shell";

export const Route = createFileRoute("/risk")({
  head: () => ({
    meta: [
      { title: "Risk Assessment — SDS Manager" },
      { name: "description", content: "Risk Assessment module for SDS Manager." },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <PageShell>
      <Placeholder title="Risk Assessment" description="Placeholder content for the Risk Assessment module." />
    </PageShell>
  );
}
