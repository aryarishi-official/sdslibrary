import type { ReactNode } from "react";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { DashboardHeader } from "@/components/dashboard-header";

export function PageShell({
  children,
  headerLeading,
}: {
  children: ReactNode;
  headerLeading?: ReactNode;
}) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background">
        <AppSidebar />
        <SidebarInset className="flex flex-1 flex-col">
          <DashboardHeader leading={headerLeading} />
          <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
            <div className="mx-auto w-full max-w-[1400px] space-y-6">{children}</div>
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}

export function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">{title}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="flex min-h-[420px] items-center justify-center rounded-xl border border-dashed bg-card/50 p-10 text-center shadow-sm">
        <div className="max-w-md space-y-2">
          <p className="text-sm font-medium text-foreground">Coming soon</p>
          <p className="text-sm text-muted-foreground">
            This section is a placeholder. Content for “{title}” will live here once the
            module is wired up.
          </p>
        </div>
      </div>
    </>
  );
}