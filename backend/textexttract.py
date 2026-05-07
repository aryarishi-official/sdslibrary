import pdfplumber


def extract_text_pdfplumber(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()
    
        




if __name__ == "__main__":
    result = extract_text_pdfplumber("uploads/nitrogen.pdf")


    with open("nitrogen.txt", "w", encoding="utf-8") as f:
        f.write(result) 
    