import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FlaskConical, ShieldCheck, Sparkles, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoginDialog } from "@/components/login-dialog";
import heroImage from "@/assets/sds.png";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SDS Library — Manage your Safety Data Sheets" },
      {
        name: "description",
        content:
          "A modern home for every Safety Data Sheet your team relies on. Upload, organise and find what you need in seconds.",
      },
    ],
  }),
  component: LandingPage,
});

const NAV_LINKS = [
  { label: "SDS Manager", href: "#" },
  { label: "Pricing", href: "#" },
  { label: "Contact", href: "#" },
];

function LandingPage() {
  const [loginOpen, setLoginOpen] = useState(false);

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      {/* Background accents */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
      >
        <div className="absolute -top-32 left-1/2 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-primary/15 blur-3xl" />
        <div className="absolute right-[-10%] top-1/3 h-[420px] w-[420px] rounded-full bg-accent/40 blur-3xl" />
      </div>

      {/* Top navigation */}
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/70 backdrop-blur-md">
        <div className="mx-auto flex h-16 w-full max-w-[1280px] items-center gap-6 px-4 md:px-8">
          <a href="/" className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <FlaskConical className="h-5 w-5" />
            </span>
            <span className="text-base font-semibold tracking-tight">sds library</span>
          </a>

          <nav className="ml-4 hidden items-center gap-1 md:flex">
            {NAV_LINKS.map((l) => (
              <a
                key={l.label}
                href={l.href}
                className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                {l.label}
              </a>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setLoginOpen(true)}
              className="text-sm"
            >
              Login
            </Button>
            <Button size="sm" variant="outline" className="hidden sm:inline-flex">
              Book a demo
            </Button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto w-full max-w-[1280px] px-4 pt-12 pb-20 md:px-8 md:pt-20 md:pb-28">
        <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-16">
          {/* Left: copy */}
          <div className="max-w-xl space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3 py-1 text-xs font-medium text-muted-foreground shadow-sm backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              SDS Management, reimagined
            </span>
            <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight md:text-5xl lg:text-6xl">
              The simplest way to manage your{" "}
              <span className="text-primary">Safety Data Sheets</span>
            </h1>
            <p className="text-base leading-relaxed text-muted-foreground md:text-lg">
              Lorem ipsum dolor sit amet, consectetur adipiscing elit. Centralise every
              SDS, keep your team compliant and find any chemical record in seconds —
              from one calm, modern dashboard.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button size="lg" onClick={() => setLoginOpen(true)} className="group">
                View my SDS library
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Button>
            </div>
            <div className="flex items-center gap-2 pt-2 text-xs text-muted-foreground">
              <ShieldCheck className="h-4 w-4" />
              GHS-ready · Trusted by EHS teams worldwide
            </div>
          </div>

          {/* Right: product shot */}
          <div className="relative">
            <div className="absolute -inset-6 -z-10 rounded-3xl bg-gradient-to-br from-primary/20 via-accent/30 to-transparent blur-2xl" />
            <div className="overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[0_30px_80px_-20px_rgba(15,23,42,0.25)]">
              <img
                src={heroImage}
                alt="SDS dashboard preview"
                width={1600}
                height={1024}
                className="h-auto w-full"
              />
            </div>
          </div>
        </div>
      </section>

      <LoginDialog open={loginOpen} onOpenChange={setLoginOpen} />
    </div>
  );
}
