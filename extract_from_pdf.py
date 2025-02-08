import PyMuPDF

def extract_text_from_pdf(pdf_path):
    # Open the PDF file
    document = fitz.open(pdf_path)
    text = ""

    # Iterate over each page
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        text += page.get_text()

    return text

# Example usage
pdf_path = "CDC Clinical Practice Guideline for Prescribing Opioids for Pain — United States, 2022 _ MMWR.pdf"
extracted_text = extract_text_from_pdf(pdf_path)

# Optionally, save the extracted text to a file
with open("cdc_guideline.txt", "w", encoding="utf-8") as text_file:
    text_file.write(extracted_text)
