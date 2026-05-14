import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  FileText,
  MapPin,
  Library,
  Search,
  ShieldCheck,
  QrCode,
  AlertTriangle,
  BarChart3,
  ShieldHalf,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

const items = [
  /* { title: "Dashboard", url: "/", icon: LayoutDashboard }, */
  { title: "All SDS", url: "/sds", icon: FileText },
  /* { title: "My Locations", url: "/locations", icon: MapPin },
  { title: "Manage SDS Library", url: "/library", icon: Library },
  { title: "Global SDS Search", url: "/search", icon: Search },
  { title: "SDS Compliance", url: "/compliance", icon: ShieldCheck },
  { title: "Manage QR Codes", url: "/qr-codes", icon: QrCode },
  { title: "Risk Assessment", url: "/risk", icon: AlertTriangle },
  { title: "Reports", url: "/reports", icon: BarChart3 }, */
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const currentPath = useRouterState({ select: (r) => r.location.pathname });

  return (
    <Sidebar collapsible="icon" className="border-r-0">
      <SidebarHeader className="border-b border-sidebar-border px-4 py-5">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground shadow-sm">
            <ShieldHalf className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold tracking-tight text-sidebar-foreground">
                My SDS Library
              </span>
              <span className="text-[11px] text-sidebar-foreground/60">
                Safety & Compliance
              </span>
            </div>
          )}
        </Link>
      </SidebarHeader>

      <SidebarContent className="px-2 py-3">
        <SidebarGroup>
          {!collapsed && (
            <SidebarGroupLabel className="text-sidebar-foreground/50">
              Workspace
            </SidebarGroupLabel>
          )}
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => {
                const active = currentPath === item.url;
                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={active}
                      tooltip={item.title}
                      className="data-[active=true]:bg-sidebar-primary data-[active=true]:text-sidebar-primary-foreground data-[active=true]:shadow-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
                    >
                      <Link to={item.url}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}