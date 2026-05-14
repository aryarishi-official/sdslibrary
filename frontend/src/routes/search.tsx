import { createFileRoute } from "@tanstack/react-router";
import { PageShell, Placeholder } from "@/components/page-shell";

export const Route = createFileRoute("/search")({
  head: () => ({
    meta: [
      { title: "Global SDS Search — SDS Manager" },
      { name: "description", content: "Global SDS Search module for SDS Manager." },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <PageShell>
      <Placeholder title="Global SDS Search" description="Placeholder content for the Global SDS Search module." />
    </PageShell>
  );
}
