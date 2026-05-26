import { useState } from "react";
import { Search } from "lucide-react";
import { PageShell } from "@/components/page-shell";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { getAuthToken } from "@/lib/auth";
import { API_BASE } from "@/lib/api"



type SearchResult = {
  id: number;
  product_name: string;
  chemical_name: string;
  cas_number: string;
  supplier: string;
  signal_word: string;
  revision_date: string;
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    try {
      setLoading(true);
      setSearched(true);
      const token = getAuthToken();
      const res = await fetch(
        `${API_BASE}/documents/search?q=${encodeURIComponent(query)}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResults(data);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <PageShell>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          Global SDS Search
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Search across all Safety Data Sheets by product name, CAS number, or
          chemical name.
        </p>
      </div>

      {/* Search bar */}
      <section className="rounded-xl border bg-card p-4 shadow-sm">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by product name, CAS#, chemical name..."
              className="h-10 rounded-lg pl-9"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
            />
          </div>
          <Button onClick={handleSearch} disabled={loading} className="gap-2">
            <Search className="h-4 w-4" />
            {loading ? "Searching..." : "Search"}
          </Button>
        </div>
      </section>

      {/* Results */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
            <span className="text-sm">Searching...</span>
          </div>
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <p className="text-sm">No results found for "{query}"</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium">Product Name</th>
                <th className="px-4 py-3 text-left font-medium">Chemical Name</th>
                <th className="px-4 py-3 text-left font-medium">CAS Number</th>
                <th className="px-4 py-3 text-left font-medium">Supplier</th>
                <th className="px-4 py-3 text-left font-medium">Signal Word</th>
                <th className="px-4 py-3 text-left font-medium">Revision Date</th>
              </tr>
            </thead>
            <tbody>
              {results.map((row) => (
                <tr key={row.id} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">{row.product_name ?? "—"}</td>
                  <td className="px-4 py-3 text-muted-foreground">{row.chemical_name ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{row.cas_number ?? "—"}</td>
                  <td className="px-4 py-3">{row.supplier ?? "—"}</td>
                  <td className="px-4 py-3">{row.signal_word ?? "—"}</td>
                  <td className="px-4 py-3 text-muted-foreground">{row.revision_date ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
}