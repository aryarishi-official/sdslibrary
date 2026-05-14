import type { ReactNode } from "react";
import { Bell, Search } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";

export function DashboardHeader({ leading }: { leading?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-md md:px-6">
      <SidebarTrigger className="text-foreground" />
      <Separator orientation="vertical" className="h-6" />
      {leading ?? <h1 className="text-base font-semibold tracking-tight">SDS Library</h1>}

      <div className="ml-auto flex items-center gap-2 md:gap-3">
        <div className="relative hidden md:block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search anything..."
            className="h-9 w-72 rounded-lg border-border bg-secondary/60 pl-9 text-sm focus-visible:bg-background"
          />
        </div>
        <Button variant="ghost" size="icon" className="relative rounded-lg">
          <Bell className="h-4 w-4" />
          <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-destructive" />
        </Button>
        <div className="flex items-center gap-2.5 rounded-lg border bg-card px-2 py-1 pr-3">
          <Avatar className="h-7 w-7">
            <AvatarFallback className="bg-primary text-xs text-primary-foreground">
              ZM
            </AvatarFallback>
          </Avatar>
          <div className="hidden flex-col leading-tight sm:flex">
            <span className="text-xs font-medium">Zara M.</span>
            <span className="text-[10px] text-muted-foreground">Admin</span>
          </div>
        </div>
      </div>
    </header>
  );
}