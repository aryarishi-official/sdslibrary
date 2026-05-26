import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { API_BASE } from "@/lib/api"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

export function SignupDialog({
    open,
    onOpenChange,
    onSwitchToLogin,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSwitchToLogin: () => void;
}) {
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [role, setRole] = useState("viewer");
    const [submitting, setSubmitting] = useState(false);

    async function handleSubmit(e: FormEvent) {
        e.preventDefault();
        setSubmitting(true);
        try {
            const response = await fetch(`${API_BASE}/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, email, password, role }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || "Signup failed");
            }
            alert("Account created successfully");
            onOpenChange(false);
            onSwitchToLogin();
        } catch (error: unknown) {
            alert(error instanceof Error ? error.message : "Signup failed");
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[420px]">
                <DialogHeader>
                    <DialogTitle>Create your account</DialogTitle>
                    <DialogDescription>
                        Start managing your Safety Data Sheets in minutes.
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-1.5">
                        <Label htmlFor="signup-name">Name</Label>
                        <Input
                            id="signup-name"
                            type="text"
                            placeholder="Jane Doe"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            required
                            autoComplete="name"
                        />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="signup-email">Email</Label>
                        <Input
                            id="signup-email"
                            type="email"
                            placeholder="you@company.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            autoComplete="email"
                        />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="signup-password">Password</Label>
                        <Input
                            id="signup-password"
                            type="password"
                            placeholder="••••••••"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            autoComplete="new-password"
                        />
                    </div>
                    <div className="space-y-1.5">
                        <Label htmlFor="signup-role">Role</Label>
                        <Select value={role} onValueChange={setRole}>
                            <SelectTrigger id="signup-role" className="w-full">
                                <SelectValue placeholder="Select a role" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="viewer">
                                    <div className="flex flex-col">
                                        <span>Viewer</span>
                                        <span className="text-xs text-muted-foreground">View only — no upload or delete</span>
                                    </div>
                                </SelectItem>
                                <SelectItem value="editor">
                                    <div className="flex flex-col">
                                        <span>Editor</span>
                                        <span className="text-xs text-muted-foreground">Upload allowed — no delete</span>
                                    </div>
                                </SelectItem>
                                <SelectItem value="admin">
                                    <div className="flex flex-col">
                                        <span>Admin</span>
                                        <span className="text-xs text-muted-foreground">Full access — upload &amp; delete</span>
                                    </div>
                                </SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <Button type="submit" className="w-full" disabled={submitting}>
                        {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Create account"}
                    </Button>
                </form>
                <p className="text-center text-sm text-muted-foreground">
                    Already have an account?{" "}
                    <button
                        type="button"
                        onClick={onSwitchToLogin}
                        className="font-medium text-primary hover:underline"
                    >
                        Login
                    </button>
                </p>
            </DialogContent>
        </Dialog>
    );
}