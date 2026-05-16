
from fastapi import FastAPI, UploadFile, File
import re
import shutil
import os
from jsonextractor_up import extract_layout_lines, layout_lines_to_text_and_kvs, extract_pdf_tables, extract_tables_camelot, extract, extract_product_name, extract_hazard_pictograms
from insert import insert_sds
from normalizers.normalize_sds import normalize_sds
from models import SDSDocument, Section, Subsection,User
from database import engine, Base
from database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
import json
import copy
# pyrefly: ignore [missing-import]
from fastapi.staticfiles import StaticFiles
from schemas import UserCreate, UserLogin
from auth import hash_password, verify_password, create_access_token
from fastapi.exceptions import HTTPException



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
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def extract_signal_word(sections: list) -> str | None:
    """
    Walk Section 2 (Hazard Identification) subsections looking for a
    'Signal word' title whose content contains 'Danger' or 'Warning'.

    Some PDF parsers concatenate the signal word with the next section title
    and hazard statements into one string, e.g.:
        "Warning Hazard Statements H280 Contains gas under pressure..."
    We handle this by checking only the FIRST whitespace-separated token,
    and also by matching the word anywhere at a word boundary.
    Falls back to scanning all sections if not found in Section 2.
    """
    target_sections = [s for s in sections if s.get("section_number") == "2"] or sections
    for sec in target_sections:
        for sub in sec.get("subsections", []):
            title = (sub.get("title") or "").strip().lower()
            if "signal" in title and "word" in title:
                content = (sub.get("content") or "").strip()
                # Take only the first token — handles merged content like
                # "Warning Hazard Statements H280 ..."
                first_token = content.split()[0] if content else ""
                for word in ("Danger", "Warning"):
                    if first_token.lower() == word.lower():
                        return word
                # Fallback: match as a standalone word anywhere in content
                for word in ("Danger", "Warning"):
                    if re.search(rf'\b{word}\b', content, re.IGNORECASE):
                        return word
    return None
@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_pw = hash_password(user.password)

    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed_pw
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User created"}

# Login
@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(
        user.password,
        db_user.password
    ):
     raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_access_token(
        data={"sub": db_user.email}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }
from auth import verify_token    
@app.get("/profile")
def profile(current_user: str = Depends(verify_token)):
    return {
        "message": "Protected route",
        "user": current_user
    }

@app.post("/analyze")
async def analyze(file: UploadFile = File(...),current_user: str = Depends(verify_token)):
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
            sec2 = next((s for s in sections if s.get("section_number") == "2"), None)
            if sec2 is not None:
                sec2["hazard_pictograms"] = pictograms

        if not product_name:
            product_name = file.filename.replace(".pdf", "")

        # Extract signal word from sections data
        signal_word = extract_signal_word(sections)

        structured = {
            "file_name": file.filename,
            "product_name": product_name,
            "hazard_pictograms": pictograms,
            "signal_word": signal_word,
            "sections": sections,
        }
    else:
        return {"error": "Unsupported file type"}

    print("data received")

    # Flatten tables into subsections so both title and content are saved
    def _flatten_tables(data):
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
                                    "content": str(val),
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
                                    "content": str(val),
                                })

            sec["subsections"] = new_subs
        return data_copy

    structured = _flatten_tables(structured)
    normalized = normalize_sds(structured)

    # Write debug JSON
    with open("structured.json", "w") as f:
        json.dump(structured, f, indent=4)

    doc = insert_sds(structured)

    """ return {"document_id": doc.id, "hazard_pictograms": doc.hazard_pictograms or []} """
    return {"document_id": doc.id, "hazard_pictograms": doc.hazard_pictograms or [], "normalized": normalized}


@app.get("/documents/{doc_id}")
def get_document(doc_id: int,current_user: str = Depends(verify_token),db: Session = Depends(get_db)):
    doc = db.query(SDSDocument).filter(SDSDocument.id == doc_id).first()

    sections = db.query(Section).filter(Section.document_id == doc_id).all()
    subsections = (
        db.query(Subsection)
        .join(Section)
        .filter(Section.document_id == doc_id)
        .all()
    )

    result = {
        "file_name": doc.file_name,
        "product_name": doc.product_name,
        "hazard_pictograms": doc.hazard_pictograms or [],
        "signal_word": doc.signal_word,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "sections": [],
        "pdf_url": f"http://localhost:8000/uploads/{doc.file_name}",
    }

    for sec in sections:
        sec_data = {
            "id": sec.id,
            "section_number": sec.section_number,
            "section_title": sec.section_title,
            "subsections": [],
        }

        for sub in subsections:
            if sub.section_id == sec.id:
                sec_data["subsections"].append({
                    "title": sub.title,
                    "content": sub.content,
                    "table": sub.table,
                    "list_items": sub.list_items,
                })

        result["sections"].append(sec_data)

    result["normalized"] = normalize_sds(result)

    return result


""" @app.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    docs = db.query(SDSDocument).order_by(SDSDocument.id.desc()).all()

    return [
        {
            "id": doc.id,
            "file_name": doc.file_name,
            "product_name": doc.product_name,
            "signal_word": doc.signal_word,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "hazard_pictograms": doc.hazard_pictograms or [],
        }
        for doc in docs
    ] """
@app.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    docs = db.query(SDSDocument).order_by(SDSDocument.id.desc()).all()

    results = []

    for doc in docs:

        sections = db.query(Section).filter(
            Section.document_id == doc.id
        ).all()

        subsections = (
            db.query(Subsection)
            .join(Section)
            .filter(Section.document_id == doc.id)
            .all()
        )

        structured = {
            "file_name": doc.file_name,
            "product_name": doc.product_name,
            "signal_word": doc.signal_word,
            "hazard_pictograms": doc.hazard_pictograms or [],
            "sections": [],
        }

        for sec in sections:

            sec_data = {
                "section_number": sec.section_number,
                "section_title": sec.section_title,
                "subsections": [],
            }

            for sub in subsections:
                if sub.section_id == sec.id:
                    sec_data["subsections"].append({
                        "title": sub.title,
                        "content": sub.content,
                    })

            structured["sections"].append(sec_data)

        normalized = normalize_sds(structured)

        results.append({
            "id": doc.id,
            "file_name": doc.file_name,
            "product_name": doc.product_name,
            "normalized": normalized,
            "signal_word": doc.signal_word,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "hazard_pictograms": doc.hazard_pictograms or [],
            "pdf_url": f"http://localhost:8000/uploads/{doc.file_name}",
        })

    return results


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):

    doc = db.query(SDSDocument).filter(SDSDocument.id == doc_id).first()

    if not doc:
        return {"error": "Document not found"}

    db.delete(doc)
    db.commit()

    return {"message": "Document deleted"}
