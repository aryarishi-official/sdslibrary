
from fastapi import FastAPI, UploadFile, File
import shutil
import os
from jsonextractor_up import  extract_layout_lines,layout_lines_to_text_and_kvs,extract_pdf_tables,extract_tables_camelot,extract, extract_product_name, extract_hazard_pictograms
from insert import insert_sds
from models import SDSDocument, Section, Subsection
from database import engine, Base
from database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends 
import json
import copy



app = FastAPI()
import models
Base.metadata.create_all(bind=engine)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get path of this file (app.py inside backend)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Go to backend/uploads
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    print("Saved at:", file_path)

    # Parse immediately
    if file.filename.endswith(".pdf"):
        pdf_tables = extract_pdf_tables(file_path)
        camelot_tables = extract_tables_camelot(file_path)
        pdf_tables.extend(camelot_tables)
        
        layout_lines = extract_layout_lines(file_path)
        sections = extract(layout_lines, pdf_tables=pdf_tables)
        product_name = extract_product_name(sections, layout_lines)

        # Extract GHS hazard pictograms
        pictograms = extract_hazard_pictograms(file_path)
        # Attach to Section 2 subsections for inline display
        if pictograms:
            sec2 = next((s for s in sections if s.get('section_number') == '2'), None)
            if sec2 is not None:
                sec2['hazard_pictograms'] = pictograms

        if not product_name:
            product_name = file.filename.replace(".pdf", "")

        structured = {
            "file_name": file.filename,
            "product_name": product_name,
            "hazard_pictograms": pictograms,
            "sections": sections
        }
    else:
        return {"error": "Unsupported file type"}

    print("data received")
    
    # Flatten tables into subsections so both title and content are saved
    def _flatten_tables(data):
        # We work on a deep copy to not modify the original if it's used elsewhere,
        # though here we just use it for json and db.
        data_copy = copy.deepcopy(data)
        for sec in data_copy.get("sections", []):
            new_subs = []
            processed_tables = []
            
            for sub in sec.get("subsections", []):
                new_subs.append(sub)
                if "table" in sub:
                    tbl = sub["table"]
                    processed_tables.append(tbl)
                    for row in tbl.get("rows", []):
                        for header in tbl.get("headers", []):
                            val = row.get(header)
                            if val is not None and str(val).strip():
                                new_subs.append({
                                    "title": str(header),
                                    "content": str(val)
                                })
            
            # Process any top-level tables that weren't inside a subsection
            for tbl in sec.get("tables", []):
                if tbl not in processed_tables:
                    for row in tbl.get("rows", []):
                        for header in tbl.get("headers", []):
                            val = row.get(header)
                            if val is not None and str(val).strip():
                                new_subs.append({
                                    "title": str(header),
                                    "content": str(val)
                                })
                                
            sec["subsections"] = new_subs
        return data_copy

    structured = _flatten_tables(structured)

    #print json in one file
    with open("structured.json", "w") as f:
        json.dump(structured, f, indent=4)

    doc = insert_sds(structured)

    return {"document_id": doc.id, "hazard_pictograms": doc.hazard_pictograms or []}
@app.get("/documents/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(SDSDocument).filter(SDSDocument.id == doc_id).first()

    sections = db.query(Section).filter(Section.document_id == doc_id).all()
    # subsections = db.query(Subsection).all()
    subsections = db.query(Subsection)\
    .join(Section)\
    .filter(Section.document_id == doc_id)\
    .all()

    result = {
        "file_name": doc.file_name,
        "product_name": doc.product_name,
        "hazard_pictograms": doc.hazard_pictograms or [],
        "sections": []
    }

    for sec in sections:
        sec_data = {
            "id": sec.id,
            "section_number": sec.section_number,
            "section_title": sec.section_title,
            "subsections": []
        }

        """ for sub in subsections:
            if sub.section_id == sec.id:
                sec_data["subsections"].append({
                    "title": sub.title,
                    "content": sub.content,
                })

        result["sections"].append(sec_data) """
        for sub in subsections:
            if sub.section_id == sec.id:
                sec_data["subsections"].append({
                    "title": sub.title,
                    "content": sub.content,
                    "table": sub.table,
                    "list_items": sub.list_items
        })
        
        result["sections"].append(sec_data)
        # sec_data["subsections"].append(subsection)

    return result
@app.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    docs = db.query(SDSDocument).all()

    return [
        {
            "id": doc.id,
            "file_name": doc.file_name,
            "product_name": doc.product_name
        }
        for doc in docs
    ]
@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(SDSDocument).filter(SDSDocument.id == doc_id).first()

    if not doc:
        return {"error": "Document not found"}

    db.delete(doc)
    db.commit()

    return {"message": "Document deleted"}

