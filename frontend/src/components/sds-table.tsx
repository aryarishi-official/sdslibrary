import {
  Eye,
  Trash2,
  Flame,
  Skull,
  AlertTriangle,
  TestTube,
  Bomb,
  Leaf,
  FileText,
  Zap,
  Wind,
  Activity,
} from "lucide-react";
import { Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type GhsPictogram = {
  ghs_code: string;
  description: string;
  source: string;
};

export type SdsRow = {
  id: number;
  product_name: string;
  pdf_url?: string;
  normalized?: {
    product_name?: string;
  };

  signal_word: string | null;
  uploaded_at: string | null;
  hazard_pictograms: GhsPictogram[];
};

// GHS code → icon + colour config
const GHS_PICTO: Record<string, { icon: typeof Flame; label: string; cls: string }> = {
  GHS01: { icon: Bomb, label: "Explosive", cls: "bg-rose-500/10 text-rose-600 ring-rose-500/30" },
  GHS02: { icon: Flame, label: "Flammable", cls: "bg-orange-500/10 text-orange-600 ring-orange-500/30" },
  GHS03: { icon: Zap, label: "Oxidizing", cls: "bg-yellow-500/10 text-yellow-600 ring-yellow-500/30" },
  GHS04: { icon: Wind, label: "Compressed Gas", cls: "bg-sky-500/10 text-sky-600 ring-sky-500/30" },
  GHS05: { icon: TestTube, label: "Corrosive", cls: "bg-fuchsia-500/10 text-fuchsia-600 ring-fuchsia-500/30" },
  GHS06: { icon: Skull, label: "Toxic", cls: "bg-red-500/10 text-red-600 ring-red-500/30" },
  GHS07: { icon: AlertTriangle, label: "Irritant / Harmful", cls: "bg-amber-500/10 text-amber-600 ring-amber-500/30" },
  GHS08: { icon: Activity, label: "Health Hazard", cls: "bg-indigo-500/10 text-indigo-600 ring-indigo-500/30" },
  GHS09: { icon: Leaf, label: "Environmental", cls: "bg-emerald-500/10 text-emerald-600 ring-emerald-500/30" },
};

function SignalBadge({ signal }: { signal: string | null }) {
  if (!signal) return <span className="text-sm text-muted-foreground">—</span>;
  const cls =
    signal.toLowerCase() === "danger"
      ? "bg-red-500/10 text-red-700 ring-red-500/30"
      : "bg-amber-500/10 text-amber-700 ring-amber-500/30";
  return (
    <span className={cn("rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset", cls)}>
      {signal}
    </span>
  );
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function SdsTable({
  rows = [],
  onDelete,
}: {
  rows?: SdsRow[];
  onDelete?: (id: number) => void;
}) {
  return (
    <TooltipProvider delayDuration={150}>
      <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
        <div className="max-h-[640px] overflow-auto">
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead className="sticky top-0 z-10 bg-secondary/70 backdrop-blur">
              <tr className="text-left">
                {["Product Name", "Signal", "Uploaded", "Pictograms", "Actions"].map((h) => (
                  <th
                    key={h}
                    className="border-b px-5 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-5 py-12 text-center text-sm text-muted-foreground"
                  >
                    No documents to show.
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr key={r.id} className="group transition-colors hover:bg-accent/40">
                  {/* Product Name */}
                  <td className="border-b px-5 py-4">
                    <Link
                      to="/sds/$id"
                      params={{ id: String(r.id) }}
                      className="font-medium text-foreground hover:underline hover:underline-offset-2"
                    >
                      {r.normalized?.product_name || r.product_name}
                    </Link>
                    <div className="text-xs text-muted-foreground">Doc #{r.id}</div>
                  </td>

                  {/* Signal Word */}
                  <td className="border-b px-5 py-4">
                    <SignalBadge signal={r.signal_word} />
                  </td>

                  {/* Uploaded Date */}
                  <td className="border-b px-5 py-4 text-muted-foreground">
                    {formatDate(r.uploaded_at)}
                  </td>

                  {/* GHS Pictograms */}
                  <td className="border-b px-5 py-4">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {(r.hazard_pictograms ?? []).length === 0 ? (
                        <span className="text-xs text-muted-foreground">—</span>
                      ) : (
                        (r.hazard_pictograms ?? []).map((p, i) => {
                          const cfg = GHS_PICTO[p.ghs_code];
                          if (!cfg) return null;
                          const Icon = cfg.icon;
                          return (
                            <Tooltip key={i}>
                              <TooltipTrigger asChild>
                                <span
                                  className={cn(
                                    "inline-flex h-7 w-7 items-center justify-center rounded-md ring-1 ring-inset",
                                    cfg.cls,
                                  )}
                                >
                                  <Icon className="h-3.5 w-3.5" />
                                </span>
                              </TooltipTrigger>
                              <TooltipContent>{cfg.label}</TooltipContent>
                            </Tooltip>
                          );
                        })
                      )}
                    </div>
                  </td>

                  {/* Actions */}
                  <td className="border-b px-5 py-4">
                    <div className="flex items-center gap-1 opacity-70 transition-opacity group-hover:opacity-100">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Link
                            to="/sds/$id"
                            params={{ id: String(r.id) }}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-foreground/80 hover:bg-accent hover:text-accent-foreground"
                          >
                            <Eye className="h-4 w-4" />
                          </Link>
                        </TooltipTrigger>
                        <TooltipContent>View details</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          {r.pdf_url ? (
                            <a
                              href={r.pdf_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-foreground/80 hover:bg-accent hover:text-accent-foreground"
                            >
                              <FileText className="h-4 w-4" />
                            </a>
                          ) : (
                            <Button size="icon" variant="ghost" className="h-8 w-8" disabled>
                              <FileText className="h-4 w-4" />
                            </Button>
                          )}
                        </TooltipTrigger>
                        <TooltipContent>
                          {r.pdf_url ? "View PDF" : "PDF not available"}
                        </TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-destructive hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => onDelete?.(r.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Delete</TooltipContent>
                      </Tooltip>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </TooltipProvider>
  );
}