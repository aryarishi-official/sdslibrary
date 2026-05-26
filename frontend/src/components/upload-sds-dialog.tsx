import { useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud,
  FileText,
  X,
  Sparkles,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
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
import { getAuthToken } from "@/lib/auth";

type Phase = "select" | "processing" | "done";

export function UploadSdsDialog({
  trigger,
  onSuccess,
}: {
  trigger: ReactNode;
  onSuccess?: () => void;
}) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("select");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [docId, setDocId] = useState<number | null>(null);

  const reset = () => {
    setPhase("select");
    setFile(null);
    setDragOver(false);
    setErrorMsg(null);
    setDocId(null);
  };

  const handleOpen = (v: boolean) => {
    if (phase === "processing") return; // prevent close while uploading
    setOpen(v);
    if (!v) reset();
  };

  const handleAnalyse = async () => {
    if (!file) return;
    setErrorMsg(null);
    setPhase("processing");

    try {
      const token = getAuthToken();
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!res.ok) throw new Error("Failed to analyze PDF");

      const data = await res.json();
      const id: number = data.document_id;

      qc.invalidateQueries({ queryKey: ["documents"] });
      onSuccess?.();

      setDocId(id);
      setPhase("done");

      // Navigate after a short moment so the user sees the success state
      setTimeout(() => {
        setOpen(false);
        reset();
        navigate(`/sds/${id}`);
      }, 900);
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Upload failed");
      setPhase("select");
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>

      <DialogContent className="sm:max-w-lg p-0 overflow-hidden">
        <div className="flex flex-col">
          {/* ── Header ─────────────────────────────────── */}
          <div className="px-6 pt-6 pb-4">
            <DialogHeader>
              <DialogTitle>Add SDS Sheet</DialogTitle>
              <DialogDescription>
                Select a Safety Data Sheet PDF to upload and extract.
              </DialogDescription>
            </DialogHeader>
          </div>

          {/* ── Body ───────────────────────────────────── */}
          <div className="px-6 pb-2 min-h-[220px] flex flex-col justify-center">
            {phase === "select" && (
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) setFile(f);
                }}
                className={cn(
                  "rounded-xl border-2 border-dashed p-6 text-center transition-colors",
                  dragOver
                    ? "border-primary bg-primary/5"
                    : "border-border bg-secondary/40",
                )}
              >
                {!file ? (
                  <div className="flex flex-col items-center gap-3 py-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <UploadCloud className="h-6 w-6" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">
                        Drag &amp; drop your SDS PDF here
                      </p>
                      <p className="text-xs text-muted-foreground">PDF up to 20 MB</p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => inputRef.current?.click()}
                    >
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
                      className="h-8 w-8 shrink-0"
                      onClick={() => setFile(null)}
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

            {phase === "processing" && (
              <div className="flex flex-col items-center justify-center gap-4 rounded-xl border bg-secondary/30 py-12 text-center">
                <div className="relative">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <Loader2 className="absolute -right-1 -top-1 h-5 w-5 animate-spin text-primary" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-semibold">Analysing {file?.name}</p>
                  <p className="text-xs text-muted-foreground">
                    Extracting hazards, pictograms, composition and regulatory data…
                  </p>
                </div>
                <div className="mt-2 grid w-full max-w-xs gap-2 text-left">
                  {[
                    "Parsing PDF structure",
                    "Identifying SDS sections",
                    "Extracting key fields",
                  ].map((t) => (
                    <div
                      key={t}
                      className="flex items-center gap-2 rounded-md bg-background px-3 py-2 text-xs ring-1 ring-border"
                    >
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {phase === "done" && (
              <div className="flex flex-col items-center justify-center gap-3 rounded-xl border bg-emerald-500/5 py-12 text-center ring-1 ring-emerald-500/20">
                <CheckCircle2 className="h-10 w-10 text-emerald-500" />
                <p className="text-sm font-semibold">Analysis complete!</p>
                <p className="text-xs text-muted-foreground">
                  Redirecting to document #{docId}…
                </p>
              </div>
            )}

            {errorMsg && phase === "select" && (
              <p className="mt-3 text-xs text-destructive">
                Upload failed: {errorMsg}
              </p>
            )}
          </div>

          {/* ── Footer ─────────────────────────────────── */}
          <DialogFooter className="gap-2 border-t bg-background px-6 py-4">
            {phase === "select" && (
              <>
                <Button variant="ghost" onClick={() => handleOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleAnalyse}
                  disabled={!file}
                  className="gap-2"
                >
                  <Sparkles className="h-4 w-4" />
                  Upload and Analyse
                </Button>
              </>
            )}
            {phase === "processing" && (
              <Button disabled className="gap-2 w-full">
                <Loader2 className="h-4 w-4 animate-spin" />
                Processing…
              </Button>
            )}
            {phase === "done" && (
              <Button disabled className="gap-2 w-full bg-emerald-500 hover:bg-emerald-500">
                <CheckCircle2 className="h-4 w-4" />
                Redirecting…
              </Button>
            )}
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}