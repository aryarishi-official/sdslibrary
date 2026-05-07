import { useState, useEffect } from "react";
import Subsection from "./components/subsection";

function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const [documents, setDocuments] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  // Fetch documents list
  useEffect(() => {
    fetch("http://127.0.0.1:8000/documents")
      .then((res) => res.json())
      .then((data) => setDocuments(data))
      .catch((err) => console.error(err));
  }, []);

  // Upload + analyze
  const uploadFile = async () => {
    if (!file) {
      alert("Please select a file");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);

    try {
      // Step 1: Upload
      const res = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        body: formData,
      });

      const { document_id } = await res.json();

      // Step 2: Fetch parsed result
      const docRes = await fetch(
        `http://127.0.0.1:8000/documents/${document_id}`
      );

      const data = await docRes.json();

      setResult(data);
      setSelectedId(document_id);

      // Refresh documents list
      fetch("http://127.0.0.1:8000/documents")
        .then((res) => res.json())
        .then((data) => setDocuments(data));
    } catch (err) {
      console.error(err);
      alert("Error uploading file");
    }

    setLoading(false);
  };

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* Sidebar */}
      <div
        style={{
          width: "260px",
          background: "#1e293b",
          color: "white",
          padding: "15px",
          overflowY: "auto",
        }}
      >
        <h3>📂 Documents</h3>

        {documents.map((doc) => (
          <div
            key={doc.id}
            onClick={async () => {
              const res = await fetch(
                `http://127.0.0.1:8000/documents/${doc.id}`
              );
              const data = await res.json();

              setResult(data);
              setSelectedId(doc.id);
            }}
            style={{
              padding: "10px",
              marginBottom: "8px",
              borderRadius: "6px",
              cursor: "pointer",
              background:
                selectedId === doc.id ? "#475569" : "transparent",
            }}
            onMouseOver={(e) => {
              if (selectedId !== doc.id)
                e.target.style.background = "#334155";
            }}
            onMouseOut={(e) => {
              if (selectedId !== doc.id)
                e.target.style.background = "transparent";
            }}
          >
            {doc.product_name || doc.file_name || `Doc ${doc.id}`}

            <button
              onClick={async (e) => {
                e.stopPropagation();

                await fetch(
                  `http://127.0.0.1:8000/documents/${doc.id}`,
                  { method: "DELETE" }
                );

                const res = await fetch("http://127.0.0.1:8000/documents");
                const data = await res.json();
                setDocuments(data);

                if (selectedId === doc.id) {
                  setResult(null);
                  setSelectedId(null);
                }
              }}
              style={{
                background: "red",
                color: "white",
                border: "none",
                borderRadius: "4px",
                padding: "5px 8px",
                cursor: "pointer",
                marginLeft: "10px",
              }}
            >
              ❌
            </button>
          </div>
        ))}

        <hr />

        {result && (
          <>
            <h4>Sections</h4>

            {result.sections?.map((sec) => (
              <div
                key={sec.id}
                style={{ padding: "8px", cursor: "pointer" }}
                onClick={() =>
                  document
                    .getElementById(`section-${sec.section_number}`)
                    ?.scrollIntoView({ behavior: "smooth" })
                }
              >
                {sec.section_number}. {sec.section_title}
              </div>
            ))}
          </>
        )}
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, padding: "20px", overflowY: "auto" }}>
        <h2>SDS Analyzer</h2>

        <input
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={(e) => setFile(e.target.files[0])}
        />

        <br />
        <br />

        <button onClick={uploadFile}>
          {loading ? "Processing..." : "Upload & Analyze"}
        </button>

        <hr />

        {/* Result */}
        {result && (
          <div>
            <h2>{result.product_name}</h2>
            <p>
              <strong>File:</strong> {result.file_name}
            </p>

            {result.sections?.map((sec) => {
              // ✅ KEY FIX: compute inside map
              const hasTable = sec.subsections?.some(
                (sub) => sub.table && sub.table.headers?.length > 0
              );

              return (
                <div
                  key={sec.id}
                  id={`section-${sec.section_number}`}
                  style={{
                    marginBottom: "20px",
                    padding: "15px",
                    borderRadius: "10px",
                    background: "#f1f5f9",
                  }}
                >
                  <h3>
                    {sec.section_number}. {sec.section_title}
                  </h3>

                  {sec.subsections && sec.subsections.length > 0 ? (
                    sec.subsections.map((sub, i) => (
                      <Subsection key={i} sub={sub} />
                    ))
                  ) : (
                    <div style={{ marginTop: "10px" }}>
                      <p>{sec.raw_content || "No content available"}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
