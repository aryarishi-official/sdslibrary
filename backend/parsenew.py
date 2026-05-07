import pytesseract
import fitz
import cv2
import numpy as np
from PIL import Image
from sectionparser import extract_sections, format_results

def extract_text_ocr(pdf_path):
    doc = fitz.open(pdf_path)
    all_text = []

    for i, page in enumerate(doc):

        print(f"Processing page {i+1}")

        #  Increase resolution (CRITICAL)
        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4))  # was 1.5 → now 3

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_cv = np.array(img)

        #  Convert to grayscale
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        #  Apply light denoising (NOT aggressive threshold)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)

        #  OTSU threshold (better than adaptive for clean docs)
        _, thresh = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        #  Better PSM mode
        custom_config = r'--oem 3 --psm 4'

        text = pytesseract.image_to_string(thresh, config=custom_config)

        all_text.append(text)

    return "\n".join(all_text)




if __name__ == "__main__":
    result = extract_text_ocr("uploads/carbon_jpg_embedded.pdf")


    with open("scannedoutput_carbon.txt", "w", encoding="utf-8") as f:
        f.write(result) 
    sections = extract_sections(result)

    print(format_results(sections, "sds")) 
