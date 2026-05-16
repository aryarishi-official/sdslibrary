from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


""" class SDSDocument(Base):
    __tablename__ = "sds_documents"

    id = Column(Integer, primary_key=True)
    file_name = Column(String)
    product_name = Column(String)
    uploaded_at = Column(DateTime, server_default=func.now())
    status = Column(String, default="processed")

    sections = relationship("Section", back_populates="document", cascade="all, delete") """

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name=Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)
class SDSDocument(Base):
    __tablename__ = "sds_documents"

    id = Column(Integer, primary_key=True)
    file_name = Column(String)
    product_name = Column(String)
    hazard_pictograms = Column(JSON, default=list)
    uploaded_at = Column(DateTime, server_default=func.now())
    signal_word = Column(String, nullable=True)

    sections = relationship(
        "Section",
        back_populates="document",
        cascade="all, delete-orphan"
    )


""" class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    sds_id = Column(Integer, ForeignKey("sds_documents.id"))

    section_number = Column(String)
    section_title = Column(String)
    
    section_order = Column(Integer)

    document = relationship("SDSDocument", back_populates="sections")
    subsections = relationship("Subsection", back_populates="section", cascade="all, delete") """

class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    section_number = Column(String)
    section_title = Column(String)

    # 🔥 ADD THIS (CRITICAL)
    document_id = Column(Integer, ForeignKey("sds_documents.id"))

    # 🔥 ADD THIS (CRITICAL)
    document = relationship(
        "SDSDocument",
        back_populates="sections"
    )

    subsections = relationship(
        "Subsection",
        back_populates="section",
        cascade="all, delete-orphan"
    )


""" class Subsection(Base):
    __tablename__ = "subsections"

    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("sections.id"))

    title = Column(String)
    content = Column(Text)
    subsection_order = Column(Integer)

    section = relationship("Section", back_populates="subsections")
 """

class Subsection(Base):
    __tablename__ = "subsections"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(Text)
    table = Column(JSON)
    list_items = Column(JSON)

    section_id = Column(Integer, ForeignKey("sections.id"))

    section = relationship(
        "Section",
        back_populates="subsections"
    )