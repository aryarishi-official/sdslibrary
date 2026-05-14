import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { Search, Calendar, Upload, Download, SlidersHorizontal } from "lucide-react";
import { PageShell } from "@/components/page-shell";
import { SdsTable, type SdsRow } from "@/components/sds-table";
import { UploadSdsDialog } from "@/components/upload-sds-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const API_BASE = "http://localhost:8000";

export const Route = createFileRoute("/sds")({
  head: () => ({
    meta: [
      { title: "All SDS — SDS Manager" },
      {
        name: "description",
        content: "Browse, upload and audit Safety Data Sheets across your facilities.",
      },
    ],
  }),
  component: AllSdsPage,
});

function AllSdsPage() {
  // Default to the "completed" tab
  const [tab, setTab] = useState<"processing" | "completed">("completed");
  const [rows, setRows] = useState<SdsRow[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDocs = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/documents`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: SdsRow[] = await res.json();
      setRows(data);
    } catch (err) {
      console.error("Failed to fetch documents:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount
  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  const handleDelete = useCallback(async (id: number) => {
    try {
      await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });
      setRows((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      console.error("Failed to delete document:", err);
    }
  }, []);

  return (
    <PageShell>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">All SDS</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Browse, upload and audit Safety Data Sheets across your facilities.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="gap-2">
            <Download className="h-4 w-4" />
            Export
          </Button>
          <UploadSdsDialog
            onSuccess={fetchDocs}
            trigger={
              <Button className="gap-2 shadow-sm">
                <Upload className="h-4 w-4" />
                Upload SDS Sheet
              </Button>
            }
          />
        </div>
      </div>

      <section className="rounded-xl border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by product, CAS#..."
              className="h-10 rounded-lg pl-9"
            />
          </div>
          <Select>
            <SelectTrigger className="h-10 w-[170px]">
              <SelectValue placeholder="Hazard Class" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All hazards</SelectItem>
              <SelectItem value="flammable">Flammable</SelectItem>
              <SelectItem value="toxic">Toxic</SelectItem>
              <SelectItem value="corrosive">Corrosive</SelectItem>
              <SelectItem value="env">Environmental</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" className="h-10 gap-2 text-muted-foreground">
            <Calendar className="h-4 w-4" />
            Date range
          </Button>
          <Button variant="ghost" size="icon" className="h-10 w-10">
            <SlidersHorizontal className="h-4 w-4" />
          </Button>
        </div>
      </section>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)} className="space-y-4">
        <TabsList className="h-10 rounded-lg bg-secondary/70 p-1">
          <TabsTrigger value="processing" className="gap-2 px-4">
            Processing
            <span className="rounded-md bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
              0
            </span>
          </TabsTrigger>
          <TabsTrigger value="completed" className="gap-2 px-4">
            Completed
            <span className="rounded-md bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700">
              {loading ? "…" : rows.length}
            </span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="processing" className="mt-0">
          <SdsTable rows={[]} onDelete={handleDelete} />
        </TabsContent>

        <TabsContent value="completed" className="mt-0">
          {loading ? (
            <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
              <div className="flex items-center justify-center py-16">
                <div className="flex flex-col items-center gap-3 text-muted-foreground">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  <span className="text-sm">Loading documents…</span>
                </div>
              </div>
            </div>
          ) : (
            <SdsTable rows={rows} onDelete={handleDelete} />
          )}
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}