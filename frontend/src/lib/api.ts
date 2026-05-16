function authHeaders() {
    const token = localStorage.getItem("token");

    return token
        ? {
            Authorization: `Bearer ${token}`,
        }
        : {};
}

export const api = {
    listDocuments: () =>
        fetch(`${API_URL}/documents`, {
            headers: authHeaders(),
        }).then(handle<DocumentListItem[]>),

    getDocument: (id: number | string) =>
        fetch(`${API_URL}/documents/${id}`, {
            headers: authHeaders(),
        }).then(handle<DocumentDetail>),

    deleteDocument: (id: number | string) =>
        fetch(`${API_URL}/documents/${id}`, {
            method: "DELETE",
            headers: authHeaders(),
        }).then(
            handle<{ message?: string; error?: string }>,
        ),

    analyze: (file: File) => {
        const fd = new FormData();
        fd.append("file", file);

        return fetch(`${API_URL}/analyze`, {
            method: "POST",
            headers: authHeaders(),
            body: fd,
        }).then(
            handle<{ document_id: number; hazard_pictograms: string[] }>,
        );
    },

    pdfUrl: (fileName: string) =>
        `${API_URL}/uploads/${encodeURIComponent(fileName)}`,
};