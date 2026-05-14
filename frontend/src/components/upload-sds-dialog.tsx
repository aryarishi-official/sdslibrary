import { useRef, useState, type ReactNode } from "react";
import { UploadCloud, FileText, X, Sparkles, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
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

const API_BASE = "http://localhost:8000";

type UploadState = "idle" | "uploading" | "success" | "error";

export function UploadSdsDialog({
  trigger,
  onSuccess,
}: {
  trigger: ReactNode;
  onSuccess?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setFile(null);
    setDragOver(false);
    setUploadState("idle");
    setErrorMsg("");
  };

  const onAnalyse = async () => {
    if (!file) return;
    setUploadState("uploading");
    setErrorMsg("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.error ?? `Server error (${res.status})`);
      }

      setUploadState("success");

      // Brief pause so user sees success, then close + refresh
      setTimeout(() => {
        setOpen(false);
        reset();
        onSuccess?.();
      }, 1200);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setErrorMsg(message);
      setUploadState("error");
    }
  };

  const submitting = uploadState === "uploading";

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Upload SDS Sheet</DialogTitle>
          <DialogDescription>
            Select a Safety Data Sheet (PDF). We'll extract hazards, pictograms and metadata
            for you.
          </DialogDescription>
        </DialogHeader>

        {/* Drop zone */}
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
                disabled={submitting}
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

        {/* Status messages */}
        {uploadState === "success" && (
          <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-700 ring-1 ring-emerald-500/30">
            <CheckCircle2 className="h-4 w-4 shrink-0" />
            SDS processed successfully!
          </div>
        )}
        {uploadState === "error" && (
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-4 py-2.5 text-sm font-medium text-destructive ring-1 ring-destructive/30">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {errorMsg || "Something went wrong. Please try again."}
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={onAnalyse} disabled={!file || submitting} className="gap-2">
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analysing…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Upload and Analyse
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}