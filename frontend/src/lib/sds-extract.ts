
export type ApiSubsection = {
  title: string;
  content: string;
  table: unknown | null;
  list_items: string[] | null;
};

export type ApiSection = {
  id: number;
  section_number: string;
  section_title: string;
  subsections: ApiSubsection[];
};

export type Pictogram = {
  ghs_code: string;
  description: string;
  source: string;
};

export type DocumentDetail = {
  file_name: string;
  product_name: string;
  signal_word: string | null;
  uploaded_at: string | null;
  hazard_pictograms: Pictogram[];
  sections: ApiSection[];
};

/** Find a section by number, tolerating trailing dots (e.g. "1.") */
export function getSection(
  sections: ApiSection[],
  num: string
): ApiSection | undefined {
  return sections.find(
    (s) => s.section_number.replace(/\.$/, "").trim() === num
  );
}

/** Return the first matching subsection content, or "—" */
export function pick(
  section: ApiSection | undefined,
  ...keywords: string[]
): string {
  if (!section) return "—";
  for (const kw of keywords) {
    const sub = section.subsections.find((s) =>
      s.title.toLowerCase().includes(kw.toLowerCase())
    );
    if (sub?.content?.trim()) return sub.content.trim();
  }
  return "—";
}

/** Like pick() but truncates long values to 220 chars */
export function pickShort(
  section: ApiSection | undefined,
  ...keywords: string[]
): string {
  const v = pick(section, ...keywords);
  return v.length > 220 ? v.slice(0, 220) + "…" : v;
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
