import React from "react";

// 🔹 Table Renderer
function renderTable(table) {
    return (
        <table border="1" style={{ width: "100%", marginBottom: "20px" }}>
            <thead>
                <tr>
                    {table.headers.map((h, i) => (
                        <th key={i}>{h}</th>
                    ))}
                </tr>
            </thead>

            <tbody>
                {table.rows.map((row, i) => (
                    <tr key={i}>
                        {table.headers.map((h, j) => (
                            <td key={j}>{row[h] || ""}</td>
                        ))}
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

// 🔹 Subsection Component
export default function Subsection({ sub }) {
    // 👉 If table exists → show title + table
    if (sub.table) {
        return (
            <div style={{ marginBottom: "10px" }}>
                {sub.title && <h4>{sub.title}</h4>}
                {renderTable(sub.table)}
            </div>
        );
    }

    // 👉 Otherwise normal content
    return (
        <div style={{ marginBottom: "10px" }}>
            {sub.title && <h4>{sub.title}</h4>}
            {sub.content && <p>{sub.content}</p>}
        </div>
    );
}

// 🔹 Basic Details Group — used by Section 16 to render the initial
//    HMIS / NFPA rating blocks as a single grouped card instead of
//    individual broken subsection headings.
export function BasicDetailsGroup({ subsections }) {
    return (
        <div
            style={{
                background: "#e2e8f0",
                borderRadius: "8px",
                padding: "12px 16px",
                marginBottom: "14px",
            }}
        >
            <h4 style={{ margin: "0 0 10px", color: "#334155" }}>
                Basic Details
            </h4>
            {subsections.map((sub, i) => (
                <div key={i} style={{ marginBottom: "8px" }}>
                    {sub.title && (
                        <strong style={{ display: "block", marginBottom: "2px" }}>
                            {sub.title}
                        </strong>
                    )}
                    {sub.content && (
                        <p style={{ margin: 0, color: "#475569" }}>{sub.content}</p>
                    )}
                </div>
            ))}
        </div>
    );
}