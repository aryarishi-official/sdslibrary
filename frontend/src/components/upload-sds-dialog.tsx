import { useRef, useState, type ReactNode } from "react";
import {
  UploadCloud,
  FileText,
  X,
  Sparkles,
  Loader2,
  Check,
  Beaker,
  CircleAlert,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";


type Step = 1 | 2 | 3;
const STEPS: { id: Step; label: string }[] = [
  { id: 1, label: "Upload PDF" },
  { id: 2, label: "Processing" },
  { id: 3, label: "Extracted data" },
];
type Subsection = {
  title: string;
  content: string | null;
};

type SectionData = {
  id: number;
  section_number: string;
  section_title: string;
  subsections: Subsection[];
};

type DocumentDetail = {
  file_name: string;
  product_name: string;
  hazard_pictograms: string[];
  sections: SectionData[];
};
export function UploadSdsDialog({ trigger }: { trigger: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>(1);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [docId, setDocId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();

  const analyze = useMutation({
    mutationFn: async (f: File) => {
      const formData = new FormData();
      formData.append("file", f);

      const token = localStorage.getItem("token");

      const res = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: token
          ? {
            Authorization: `Bearer ${token}`,
          }
          : {},
        body: formData,
      });

      if (!res.ok) {
        throw new Error("Failed to analyze PDF");
      }

      return res.json();
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      setDocId(res.document_id);
      setStep(3);
    },
    onError: (e: Error) => {
      setErrorMsg(e.message);
      setStep(1);
    },
  });

  const detail = useQuery({
    queryKey: ["document", docId],
    queryFn: async () => {
      const token = localStorage.getItem("token");

      const res = await fetch(
        `http://localhost:8000/documents/${docId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!res.ok) {
        throw new Error("Failed to fetch document");
      }

      return res.json();
    },
    enabled: step === 3 && docId != null,
  });

  const reset = () => {
    setStep(1);
    setFile(null);
    setDragOver(false);
    setErrorMsg(null);
    setDocId(null);
  };

  const onAnalyse = () => {
    if (!file) return;
    setErrorMsg(null);
    setStep(2);
    analyze.mutate(file);
  };

  const submitting = analyze.isPending;
  const close = () => {
    setOpen(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (submitting) return;
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-hidden p-0 sm:max-w-2xl">
        <div className="flex max-h-[90vh] flex-col">
          <div className="px-6 pt-6">
            <DialogHeader>
              <DialogTitle>Upload SDS Sheet</DialogTitle>
              <DialogDescription>
                Upload, process and review the extracted Safety Data Sheet in three steps.
              </DialogDescription>
            </DialogHeader>
            <Stepper current={step} />
          </div>

          <div className="flex-1 overflow-y-auto px-6 pb-2">
            {step === 1 && (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) setFile(f);
                }}
                className={cn(
                  "rounded-xl border-2 border-dashed p-6 text-center transition-colors",
                  dragOver ? "border-primary bg-primary/5" : "border-border bg-secondary/40",
                )}
              >
                {!file ? (
                  <div className="flex flex-col items-center gap-3 py-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <UploadCloud className="h-6 w-6" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">Drag & drop your SDS file here</p>
                      <p className="text-xs text-muted-foreground">PDF up to 20 MB</p>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
                      Browse files
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 rounded-lg bg-background p-3 text-left ring-1 ring-border">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {(file.size / 1024 / 1024).toFixed(2)} MB · ready to analyse
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => setFile(null)}
                      aria-label="Remove file"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                )}
                <input
                  ref={inputRef}
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setFile(f);
                    e.target.value = "";
                  }}
                />
              </div>
            )}

            {step === 2 && (
              <ProcessingPanel fileName={file?.name ?? "document.pdf"} />
            )}

            {step === 3 && (
              <ExtractedPanel
                isLoading={detail.isLoading}
                error={detail.error as Error | null}
                data={detail.data}
              />
            )}

            {errorMsg && step === 1 && (
              <p className="mt-3 text-xs text-destructive">Upload failed: {errorMsg}</p>
            )}
          </div>

          <DialogFooter className="gap-2 border-t bg-background px-6 py-4 sm:gap-2">
            {step === 1 && (
              <>
                <Button variant="ghost" onClick={close}>
                  Cancel
                </Button>
                <Button onClick={onAnalyse} disabled={!file} className="gap-2">
                  <Sparkles className="h-4 w-4" />
                  Upload and Analyse
                </Button>
              </>
            )}
            {step === 2 && (
              <Button disabled className="gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Processing…
              </Button>
            )}
            {step === 3 && (
              <>
                <Button variant="ghost" onClick={() => { reset(); }}>
                  Upload another
                </Button>
                <Button onClick={close}>Done</Button>
              </>
            )}
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Stepper({ current }: { current: Step }) {
  return (
    <div className="mt-4 flex items-center gap-2">
      {STEPS.map((s, i) => {
        const done = current > s.id;
        const active = current === s.id;
        return (
          <div key={s.id} className="flex flex-1 items-center gap-2">
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ring-1 ring-inset transition-colors",
                done && "bg-primary text-primary-foreground ring-primary",
                active && "bg-primary/10 text-primary ring-primary/40",
                !done && !active && "bg-secondary text-muted-foreground ring-border",
              )}
            >
              {done ? <Check className="h-3.5 w-3.5" /> : s.id}
            </div>
            <span
              className={cn(
                "truncate text-xs font-medium",
                active ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {s.label}
            </span>
            {i < STEPS.length - 1 && (
              <div className={cn("h-px flex-1", done ? "bg-primary" : "bg-border")} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ProcessingPanel({ fileName }: { fileName: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border bg-secondary/30 px-6 py-12 text-center">
      <div className="relative">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="h-6 w-6" />
        </div>
        <Loader2 className="absolute -right-1 -top-1 h-5 w-5 animate-spin text-primary" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold">Analysing {fileName}</p>
        <p className="text-xs text-muted-foreground">
          Extracting hazards, pictograms, composition and regulatory data…
        </p>
      </div>
      <div className="mt-2 grid w-full max-w-sm gap-2 text-left">
        {["Parsing PDF structure", "Identifying SDS sections", "Extracting key fields"].map(
          (t) => (
            <div
              key={t}
              className="flex items-center gap-2 rounded-md bg-background px-3 py-2 text-xs ring-1 ring-border"
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              <span>{t}</span>
            </div>
          ),
        )}
      </div>
    </div>
  );
}

function ExtractedPanel({
  isLoading,
  error,
  data,
}: {
  isLoading: boolean;
  error: Error | null;
  data: DocumentDetail | undefined;
}) {
  if (isLoading) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading extracted data…
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        <CircleAlert className="mt-0.5 h-4 w-4" />
        <div>
          <p className="font-medium">Couldn’t load extracted data</p>
          <p className="text-xs opacity-80">{error.message}</p>
        </div>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-3">
      <div className="rounded-xl border bg-card p-4 shadow-sm">
        <div className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
          Product
        </div>
        <h3 className="mt-1 text-lg font-semibold tracking-tight">{data.product_name}</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">{data.file_name}</p>
        {data.hazard_pictograms?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {data.hazard_pictograms.map((p: any, idx: number) => (
              <span
                key={`${p.ghs_code || "picto"}-${idx}`}
                className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground"
              >
                {typeof p === "object"
                  ? `${p.ghs_code ?? ""} - ${p.description ?? ""}`
                  : p}
              </span>
            ))}
          </div>
        )}
      </div>

      {data.sections.map((s) => (
        <section
          key={s.id}
          className="overflow-hidden rounded-xl border bg-card shadow-sm"
        >
          <div className="grid grid-cols-1 md:grid-cols-[220px_1fr]">
            <div className="flex items-start gap-2 border-b bg-secondary/30 p-4 md:border-b-0 md:border-r">
              <Beaker className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  Section {s.section_number}
                </div>
                <h4 className="text-sm font-semibold tracking-tight">
                  {s.section_title}
                </h4>
              </div>
            </div>
            <dl className="divide-y">
              {s.subsections.length === 0 && (
                <div className="px-5 py-3 text-xs text-muted-foreground">
                  No data extracted.
                </div>
              )}
              {s.subsections.map((sub, idx) => (
                <div
                  key={`${sub.title}-${idx}`}
                  className="grid grid-cols-1 gap-1 px-5 py-3 sm:grid-cols-[180px_1fr] sm:gap-4"
                >
                  <dt className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {sub.title}
                  </dt>
                  <dd className="whitespace-pre-wrap text-sm text-foreground">
                    {typeof sub.content === "object"
                      ? JSON.stringify(sub.content, null, 2)
                      : sub.content ?? "—"}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      ))}
    </div>
  );
}