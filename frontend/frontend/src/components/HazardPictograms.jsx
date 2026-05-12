import React from "react";

// GHS code → { emoji, color (hue), label }
const GHS_META = {
  GHS01: { emoji: "💥", color: "#ef4444", label: "Explosive" },
  GHS02: { emoji: "🔥", color: "#f97316", label: "Flammable" },
  GHS03: { emoji: "🔆", color: "#eab308", label: "Oxidizing" },
  GHS04: { emoji: "🫙", color: "#3b82f6", label: "Compressed Gas" },
  GHS05: { emoji: "⚗️", color: "#8b5cf6", label: "Corrosive" },
  GHS06: { emoji: "☠️", color: "#1e293b", label: "Acute Toxicity" },
  GHS07: { emoji: "❗", color: "#f59e0b", label: "Irritant / Harmful" },
  GHS08: { emoji: "⚕️", color: "#ec4899", label: "Health Hazard" },
  GHS09: { emoji: "🌊", color: "#06b6d4", label: "Environmental Hazard" },
  UNKNOWN: { emoji: "⚠️", color: "#94a3b8", label: "Unknown Hazard" },
};

function PictogramCard({ pictogram }) {
  const meta = GHS_META[pictogram.ghs_code] || GHS_META.UNKNOWN;
  const label = pictogram.description || meta.label;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        width: "100px",
        padding: "12px 8px 10px",
        borderRadius: "10px",
        border: `2px solid ${meta.color}`,
        background: `${meta.color}14`,
        boxShadow: `0 2px 8px ${meta.color}30`,
        textAlign: "center",
        gap: "6px",
        transition: "transform 0.15s ease, box-shadow 0.15s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-3px)";
        e.currentTarget.style.boxShadow = `0 6px 16px ${meta.color}50`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = `0 2px 8px ${meta.color}30`;
      }}
    >
      {/* Diamond shape container */}
      <div
        style={{
          width: "52px",
          height: "52px",
          background: meta.color,
          borderRadius: "6px",
          transform: "rotate(45deg)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            transform: "rotate(-45deg)",
            fontSize: "22px",
            lineHeight: 1,
          }}
        >
          {meta.emoji}
        </span>
      </div>

      {/* GHS Code */}
      <span
        style={{
          fontSize: "11px",
          fontWeight: 700,
          color: meta.color,
          letterSpacing: "0.5px",
          marginTop: "4px",
        }}
      >
        {pictogram.ghs_code}
      </span>

      {/* Description */}
      <span
        style={{
          fontSize: "10px",
          color: "#475569",
          lineHeight: 1.3,
          fontWeight: 500,
        }}
      >
        {label}
      </span>
    </div>
  );
}

export default function HazardPictograms({ pictograms }) {
  if (!pictograms || pictograms.length === 0) return null;

  return (
    <div
      style={{
        marginBottom: "18px",
        padding: "16px 18px",
        borderRadius: "10px",
        background: "linear-gradient(135deg, #fff7ed 0%, #fef2f2 100%)",
        border: "1px solid #fecaca",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          marginBottom: "14px",
        }}
      >
        <span style={{ fontSize: "16px" }}>⚠️</span>
        <strong style={{ color: "#dc2626", fontSize: "14px", letterSpacing: "0.3px" }}>
          GHS Hazard Pictograms
        </strong>
        <span
          style={{
            marginLeft: "auto",
            fontSize: "11px",
            color: "#94a3b8",
            fontStyle: "italic",
          }}
        >
          {pictograms.length} pictogram{pictograms.length !== 1 ? "s" : ""} detected
        </span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "12px" }}>
        {pictograms.map((p, i) => (
          <PictogramCard key={`${p.ghs_code}-${i}`} pictogram={p} />
        ))}
      </div>
    </div>
  );
}
