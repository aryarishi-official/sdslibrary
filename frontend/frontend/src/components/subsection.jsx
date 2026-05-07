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
    // 👉 If table exists → show table ONLY
    if (sub.table) {
        return renderTable(sub.table);
    }

    // 👉 Otherwise normal content
    return (
        <div style={{ marginBottom: "10px" }}>
            {sub.title && <h4>{sub.title}</h4>}
            {sub.content && <p>{sub.content}</p>}
        </div>
    );
}