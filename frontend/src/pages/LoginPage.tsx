import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { FlaskConical, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SignupDialog } from "@/components/signup-dialog";
import { API_BASE } from "@/lib/api"

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
      <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.24 1.4-1.7 4.1-5.5 4.1-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.5 14.6 2.5 12 2.5 6.8 2.5 2.6 6.7 2.6 12S6.8 21.5 12 21.5c6.9 0 9.4-4.8 9.4-7.4 0-.5 0-.9-.1-1.3H12z" />
    </svg>
  );
}

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [signupOpen, setSignupOpen] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/login` {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Login failed");
      }
      localStorage.setItem("token", data.access_token);
      setSubmitting(false);
      navigate("/sds");
    } catch (error: unknown) {
      setSubmitting(false);
      alert(error instanceof Error ? error.message : "Login failed");
    }
  }

  function handleGoogle() {
    navigate("/sds");
  }

  return (
    <>
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-[420px] space-y-6">
          {/* Logo */}
          <div className="flex flex-col items-center gap-2 text-center">
            <Link to="/" className="flex items-center gap-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
                <FlaskConical className="h-5 w-5" />
              </span>
            </Link>
            <h1 className="text-xl font-semibold tracking-tight">Sign in to SDS Library</h1>
            <p className="text-sm text-muted-foreground">
              Welcome back. Continue with Google or your email.
            </p>
          </div>

          <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
            <Button type="button" variant="outline" className="w-full" onClick={handleGoogle}>
              <GoogleIcon />
              Continue with Google
            </Button>
            <div className="relative my-1">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-card px-2 text-muted-foreground">or</span>
              </div>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="login-email">Email</Label>
                <Input
                  id="login-email"
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="login-password">Password</Label>
                  <a className="text-xs text-muted-foreground hover:text-foreground" href="#">
                    Forgot?
                  </a>
                </div>
                <Input
                  id="login-password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </div>
              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Login"}
              </Button>
            </form>
            <p className="text-center text-sm text-muted-foreground">
              Don't have an account?{" "}
              <button
                type="button"
                onClick={() => setSignupOpen(true)}
                className="font-medium text-primary hover:underline"
              >
                Create an account
              </button>
            </p>
          </div>
        </div>
      </div>

      <SignupDialog
        open={signupOpen}
        onOpenChange={setSignupOpen}
        onSwitchToLogin={() => {
          setSignupOpen(false);
        }}
      />
    </>
  );
}
