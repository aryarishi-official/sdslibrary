/**
 * Shared auth helpers — reads from both localStorage (remember-me) and
 * sessionStorage (session-only) so every component stays in sync.
 */

export function getAuthToken(): string | null {
  return localStorage.getItem("token") ?? sessionStorage.getItem("token");
}

/** Guard against the literal string "undefined" being stored */
function validValue(v: string | null): string | null {
  if (!v || v === "undefined" || v === "null") return null;
  return v;
}

export function getRole(): string {
  // Prefer the explicitly stored role set by saveSession in login-dialog
  const stored = validValue(
    localStorage.getItem("role") ?? sessionStorage.getItem("role")
  );
  if (stored) return stored.toLowerCase();

  // Fallback: decode JWT payload
  try {
    const token = getAuthToken();
    if (token) {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const role = payload.role;
      if (role && role !== "undefined") return role.toLowerCase();
    }
  } catch {
    // ignore
  }
  return "viewer";
}

export function getUserName(): string {
  const stored = validValue(
    localStorage.getItem("name") ?? sessionStorage.getItem("name")
  );
  if (stored) return stored;

  // Fallback: decode JWT payload
  try {
    const token = getAuthToken();
    if (token) {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const name = payload.name ?? payload.sub;
      if (name && name !== "undefined") return name;
    }
  } catch {
    // ignore
  }
  return "User";
}

export function clearSession(): void {
  ["token", "role", "name", "rememberMe"].forEach((k) => {
    localStorage.removeItem(k);
    sessionStorage.removeItem(k);
  });
}

/** Returns initials (up to 2 chars) for the avatar fallback */
export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";
}

/** Role capability checks */
export const can = {
  upload: (role: string) => role === "admin" || role === "editor",
  delete: (role: string) => role === "admin",
  view: (_role: string) => true,
};
