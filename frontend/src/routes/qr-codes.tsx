import { createFileRoute } from "@tanstack/react-router";
import { PageShell, Placeholder } from "@/components/page-shell";

export const Route = createFileRoute("/qr-codes")({
  head: () => ({
    meta: [
      { title: "Manage QR Codes — SDS Manager" },
      { name: "description", content: "Manage QR Codes module for SDS Manager." },
    ],
  }),
  component: Page,
});

function Page() {
  return (
    <PageShell>
      <Placeholder title="Manage QR Codes" description="Placeholder content for the Manage QR Codes module." />
    </PageShell>
  );
}
