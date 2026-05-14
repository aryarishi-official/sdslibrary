import { createFileRoute } from "@tanstack/react-router";
import { PageShell, Placeholder } from "@/components/page-shell";

export const Route = createFileRoute("/locations")({
  head: () => ({
    meta: [
      { title: "Locations — SDS Manager" },
      { name: "description", content: "Locations module for SDS Manager." },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <PageShell>
      <Placeholder title="Locations" description="Placeholder content for the Locations module." />
    </PageShell>
  );
}
