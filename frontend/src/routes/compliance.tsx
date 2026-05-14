import { createFileRoute } from "@tanstack/react-router";
import { PageShell, Placeholder } from "@/components/page-shell";

export const Route = createFileRoute("/compliance")({
  head: () => ({
    meta: [
      { title: "SDS Compliance — SDS Manager" },
      { name: "description", content: "SDS Compliance module for SDS Manager." },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <PageShell>
      <Placeholder title="SDS Compliance" description="Placeholder content for the SDS Compliance module." />
    </PageShell>
  );
}
