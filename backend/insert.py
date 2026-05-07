from database import engine,Base
import json
from database import SessionLocal
from models import SDSDocument, Section, Subsection



Base.metadata.create_all(bind=engine)

def insert_sds(json_data):
    db = SessionLocal()

    # Create main document
    doc = SDSDocument(
        file_name=json_data.get("file_name"),
        product_name=json_data.get("product_name")
    )

    for i, sec in enumerate(json_data["sections"]):
        section = Section(
            section_number=sec.get("section_number"),
            section_title=sec.get("section_title"),
            
            # section_order=i + 1
        )

        for j, sub in enumerate(sec.get("subsections", [])):
            """ subsection = Subsection(
                title=sub.get("title"),
                content=sub.get("content"),
                subsection_order=j + 1
            ) """
            subsection = Subsection(
                title=sub.get("title"),
                content=sub.get("content"),
                table=sub.get("table"),
                list_items=sub.get("list_items"),
                #subsection_order=j + 1
            )
            section.subsections.append(subsection)

        doc.sections.append(section)

    db.add(doc)
    db.commit()
    db.refresh(doc)
    print(f"Successfully inserted SDS: {doc.product_name} (ID: {doc.id})")
    db.close()
    print("DOC:", doc)
    print("DOC ID:", doc.id)
    return doc


if __name__ == "__main__":
    with open("extracted_sds.json") as f:
        data = json.load(f)

    insert_sds(data)

