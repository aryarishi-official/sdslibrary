import { useParams } from "react-router-dom";
import { Link } from "react-router-dom";
import { useEffect, useState, type ReactNode } from "react";
import { getAuthToken } from "@/lib/auth";
import {
  ArrowLeft, FileText, Hash,
  Bomb, Flame, Zap, Wind, TestTube, Skull, AlertTriangle, Activity, Leaf,
  Building2, ShieldAlert, Microscope, Thermometer, Eye, Package,
} from "lucide-react";
import { PageShell } from "@/components/page-shell";
import { cn } from "@/lib/utils";
import {
  type DocumentDetail,
  getSection, pick, pickShort, formatDate,
} from "@/lib/sds-extract";

import { API_BASE } from "@/lib/api"


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

// ── Small UI primitives ───────────────────────────────────────────────────────

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 px-5 py-3 sm:grid-cols-[220px_1fr] sm:gap-4">
      <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm text-foreground">{value ?? "—"}</dd>
    </div>
  );
}

function InfoCard({
  icon,
  label,
  children,
}: {
  icon: ReactNode;
  label: string;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-sm">
      <div className="grid grid-cols-1 md:grid-cols-[260px_1fr]">
        <div className="flex items-start gap-2 border-b bg-secondary/30 p-5 md:border-b-0 md:border-r">
          <span className="mt-0.5 text-muted-foreground">{icon}</span>
          <h2 className="text-sm font-semibold tracking-tight">{label}</h2>
        </div>
        <dl className="divide-y">{children}</dl>
      </div>
    </section>
  );
}

function Spinner() {
  return (
    <div className="flex items-center justify-center rounded-xl border bg-card py-16">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
        <span className="text-sm">Loading…</span>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function SdsDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<"key" | "data" | "pdf">("key");
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [showComparePdf, setShowComparePdf] = useState(false);

  useEffect(() => {
    const token = getAuthToken();
    setLoading(true);
    fetch(`${API_BASE}/documents/${id}`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then((r) => r.json())
      .then((d: DocumentDetail) => setDoc(d))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const TABS = [
    { id: "key" as const, label: "Key details" },
    { id: "data" as const, label: "Extracted data" },
    { id: "pdf" as const, label: "SDS PDF" },
  ];

  const sec1 = doc ? getSection(doc.sections, "1") : undefined;
  const sec2 = doc ? getSection(doc.sections, "2") : undefined;
  const sec3 = doc ? getSection(doc.sections, "3") : undefined;
  const sec4 = doc ? getSection(doc.sections, "4") : undefined;
  const sec8 = doc ? getSection(doc.sections, "8") : undefined;
  const sec9 = doc ? getSection(doc.sections, "9") : undefined;

  const signalWord = doc?.signal_word ?? null;
  const signalCls =
    signalWord?.toLowerCase() === "danger"
      ? "bg-red-500/10 text-red-700 ring-red-500/30"
      : "bg-amber-500/10 text-amber-700 ring-amber-500/30";

  return (
    <PageShell
      headerLeading={
        <Link
          to="/sds"
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-sm font-medium text-foreground/80 transition-colors hover:bg-accent hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to All SDS
        </Link>
      }
    >
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="rounded-xl border bg-card p-6 shadow-sm">
        {loading ? (
          <div className="animate-pulse space-y-2">
            <div className="h-3 w-40 rounded bg-secondary" />
            <div className="h-8 w-80 rounded bg-secondary" />
            <div className="h-3 w-56 rounded bg-secondary" />
          </div>
        ) : (
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 space-y-2">
              <div className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                <span>SDS</span>
                <span>·</span>
                <span>#{id}</span>
                {(() => {
                  const sup = pick(sec1, "company", "supplier", "manufacturer", "producer");
                  return sup !== "—" ? (
                    <>
                      <span>·</span>
                      <span className="max-w-[260px] truncate">{sup}</span>
                    </>
                  ) : null;
                })()}
              </div>
              <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
                {doc?.normalized?.product_name || doc?.product_name || doc?.file_name || `SDS #${id}`}
              </h1>
              <div className="font-mono text-xs text-muted-foreground">
                {doc?.file_name} · Uploaded {formatDate(doc?.uploaded_at)}
              </div>
            </div>
            {signalWord && (
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset",
                  signalCls
                )}
              >
                <span className="h-2 w-2 rounded-full bg-current opacity-80" />
                {signalWord}
              </span>
            )}
          </div>
        )}
      </section>

      {/* ── Tab bar ──────────────────────────────────────────────────────── */}
      <div className="border-b">
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              id={`tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={cn(
                "relative -mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                tab === t.id
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Key Details ──────────────────────────────────────────────────── */}
      {tab === "key" && (
        <div className="space-y-3">
          {loading ? (
            <Spinner />
          ) : (
            <>
              {/* 1. Product Identification */}
              <InfoCard icon={<Building2 className="h-4 w-4" />} label="Product Identification">
                <Row
                  label="Product Name"
                  value={doc?.normalized?.product_name || doc?.product_name || "—"}
                />
                <Row label="Trade Name / SRM Name" value={pick(sec1, "trade name", "srm name", "commercial name")} />
                <Row label="Product Identifier" value={pick(sec1, "product identifier", "product code", "srm number", "article no")} />
                <Row label="Manufacturer / Supplier" value={pick(sec1, "company", "supplier", "manufacturer", "producer")} />
                <Row label="Recommended Use" value={doc?.normalized?.recommended_use || "—"} />
                <Row label="Revision Date" value={doc?.normalized?.revision_date || "—"} />
                <Row label="SDS Version" value={pick(sec1, "version", "revision no", "sds version")} />
                <Row label="Upload ID" value={`#${id}`} />
              </InfoCard>

              {/* 2. Hazard Summary */}
              <InfoCard icon={<ShieldAlert className="h-4 w-4" />} label="Hazard Summary">
                <Row
                  label="Signal Word"
                  value={
                    signalWord ? (
                      <span className={cn("rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset", signalCls)}>
                        {signalWord}
                      </span>
                    ) : "—"
                  }
                />
                <Row label="GHS Classification" value={pickShort(sec2, "classification", "hazard class")} />
                <Row label="Hazard Statements" value={pickShort(sec2, "hazard statement", "h statement", "h-statement")} />
                <Row label="Precautionary Statements" value={pickShort(sec2, "precautionary", "p statement", "p-statement")} />
              </InfoCard>

              {/* 3. GHS Pictograms */}
              {doc && doc.hazard_pictograms.length > 0 && (
                <section className="overflow-hidden rounded-xl border bg-card shadow-sm">
                  <div className="grid grid-cols-1 md:grid-cols-[260px_1fr]">
                    <div className="flex items-start gap-2 border-b bg-secondary/30 p-5 md:border-b-0 md:border-r">
                      <Zap className="mt-0.5 h-4 w-4 text-muted-foreground" />
                      <h2 className="text-sm font-semibold tracking-tight">GHS Pictograms</h2>
                    </div>
                    <div className="flex flex-wrap gap-6 p-6">
                      {doc.hazard_pictograms.map(({ ghs_code }) => {
                        const cfg = GHS_PICTO[ghs_code];
                        if (!cfg) return null;
                        const Icon = cfg.icon;
                        return (
                          <div key={ghs_code} className="flex flex-col items-center gap-2">
                            <span className={cn("flex h-14 w-14 items-center justify-center rounded-xl ring-1 ring-inset", cfg.cls)}>
                              <Icon className="h-7 w-7" />
                            </span>
                            <span className="max-w-[72px] text-center text-[11px] font-medium leading-tight text-muted-foreground">
                              {cfg.label}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </section>
              )}

              {/* 4. Chemical Information */}
              <InfoCard icon={<Microscope className="h-4 w-4" />} label="Chemical Information">
                <Row label="CAS Number(s)" value={doc?.normalized?.cas_number || "—"} />
                <Row label="EC Number" value={pick(sec3, "ec number", "einecs", "ec no") !== "—" ? pick(sec3, "ec number", "einecs", "ec no") : "N/A"} />
                <Row label="UN Number" value={doc?.normalized?.un_number || "—"} />
                <Row label="Chemical Formula" value={pick(sec3, "formula", "molecular formula")} />
                <Row label="Substance / Mixture" value={pick(sec3, "substance", "mixture", "type of")} />
                <Row label="Concentration" value={pick(sec3, "concentration", "percentage", "weight %")} />
              </InfoCard>

              {/* 5. Physical & Chemical Properties */}
              <InfoCard icon={<Thermometer className="h-4 w-4" />} label="Physical & Chemical Properties">
                <Row label="Physical State" value={pick(sec9, "physical state", "form", "appearance")} />
                <Row label="Color" value={pick(sec9, "color", "colour")} />
                <Row label="Odor" value={pick(sec9, "odor", "odour", "smell")} />
                <Row label="pH" value={pick(sec9, "ph")} />
                <Row label="Boiling Point" value={pick(sec9, "boiling", "boil")} />
                <Row label="Flash Point" value={pick(sec9, "flash")} />
                <Row label="Density" value={pick(sec9, "density", "relative density", "specific gravity")} />
                <Row label="Solubility" value={pick(sec9, "solubility", "soluble", "water solub")} />
              </InfoCard>

              {/* 6. Exposure & Protection */}
              <InfoCard icon={<Eye className="h-4 w-4" />} label="Exposure & Protection">
                <Row label="Exposure Limits" value={pickShort(sec8, "exposure limit", "oel", "pel", "tlv", "acgih", "osha perm")} />
                <Row label="Required PPE" value={pick(sec8, "ppe", "protective equipment", "personal protective") !== "—" ? pick(sec8, "ppe", "protective equipment", "personal protective") : "Not applicable"} />
                <Row label="Ventilation" value={pick(sec8, "ventilation")} />
                <Row label="Respiratory" value={pick(sec8, "respiratory")} />
                <Row label="Eye / Hand Protection" value={pick(sec8, "eye protection", "hand protection", "glove", "face shield")} />
              </InfoCard>

              {/* 7. First Aid Measures */}
              <InfoCard icon={<Package className="h-4 w-4" />} label="First Aid Measures">
                <Row label="Eye contact" value={pickShort(sec4, "eye contact", "eye")} />
                <Row label="Skin Contact" value={pickShort(sec4, "skin contact", "skin")} />
                <Row label="Eye Contact" value={pickShort(sec4, "eye contact", "eye")} />
                <Row label="Ingestion" value={pickShort(sec4, "ingestion", "swallowed")} />
                <Row label="Medical Notes" value={pick(sec4, "medical notes", "physician notes")} />
              </InfoCard>
            </>
          )}
        </div>
      )}

      {/* ── Extracted Data ────────────────────────────────────────────────── */}
      {tab === "data" && (
        <div className="space-y-3">
          {!loading && (
            <div className="flex justify-end">
              <button
                onClick={() => setShowComparePdf((v) => !v)}
                className="rounded-md border px-4 py-2 text-sm font-medium transition hover:bg-accent"
              >
                {showComparePdf ? "Hide PDF Compare" : "Compare with PDF"}
              </button>
            </div>
          )}

          {loading ? (
            <Spinner />
          ) : (
            <div
              className={cn(
                "gap-4",
                showComparePdf ? "grid grid-cols-1 xl:grid-cols-2" : "block"
              )}
            >
              {/* LEFT SIDE — EXTRACTED DATA */}
              <div className="space-y-3">
                {doc?.sections.map((sec) => (
                  <section
                    key={sec.id}
                    className="overflow-hidden rounded-xl border bg-card shadow-sm"
                  >
                    <div className="grid grid-cols-1 md:grid-cols-[260px_1fr]">
                      <div className="flex items-start gap-2 border-b bg-secondary/30 p-5 md:border-b-0 md:border-r">
                        <Hash className="mt-0.5 h-4 w-4 text-muted-foreground" />
                        <div>
                          <span className="text-[10px] font-mono text-muted-foreground">
                            §{sec.section_number}
                          </span>
                          <h2 className="text-sm font-semibold tracking-tight">
                            {sec.section_title}
                          </h2>
                        </div>
                      </div>

                      <dl className="divide-y">
                        {sec.subsections
                          .filter((s) => s.content?.trim())
                          .map((sub, i) => (
                            <div
                              key={i}
                              className="grid grid-cols-1 gap-1 px-5 py-3 sm:grid-cols-[220px_1fr] sm:gap-4"
                            >
                              <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                                {sub.title}
                              </dt>
                              <dd className="text-sm text-foreground">
                                {sub.content}
                              </dd>
                            </div>
                          ))}

                        {sec.subsections.every((s) => !s.content?.trim()) && (
                          <div className="px-5 py-4 text-sm text-muted-foreground italic">
                            No text content extracted for this section.
                          </div>
                        )}
                      </dl>
                    </div>
                  </section>
                ))}
              </div>

              {/* RIGHT SIDE — PDF VIEWER */}
              {showComparePdf && (
                <div className="sticky top-4 h-[85vh] overflow-hidden rounded-xl border bg-card shadow-sm">
                  {doc?.file_name ? (
                    <iframe
                      src={`${API_BASE}/uploads/${doc.file_name}`}
                      title="PDF Compare Viewer"
                      className="h-full w-full"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                      PDF not available
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── PDF Tab ───────────────────────────────────────────────────────── */}
      {tab === "pdf" && (
        <section className="flex min-h-[640px] items-center justify-center rounded-xl border bg-card p-2 shadow-sm">
          <div className="flex h-[640px] w-full items-center justify-center rounded-lg border border-dashed bg-secondary/30 text-center">
            <div className="max-w-md space-y-2 px-6">
              <FileText className="mx-auto h-8 w-8 text-muted-foreground" />
              <p className="text-sm font-medium">SDS PDF preview</p>
              <p className="text-sm text-muted-foreground">
                The uploaded Safety Data Sheet PDF would render in an embedded viewer here.
              </p>
            </div>
          </div>
        </section>
      )}
    </PageShell>
  );
}
