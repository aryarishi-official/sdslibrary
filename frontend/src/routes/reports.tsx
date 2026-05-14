import { createFileRoute } from "@tanstack/react-router";
import { PageShell, Placeholder } from "@/components/page-shell";

export const Route = createFileRoute("/reports")({
  head: () => ({
    meta: [
      { title: "Reports — SDS Manager" },
      { name: "description", content: "Reports module for SDS Manager." },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <PageShell>
      <Placeholder title="Reports" description="Placeholder content for the Reports module." />
    </PageShell>
  );
}
