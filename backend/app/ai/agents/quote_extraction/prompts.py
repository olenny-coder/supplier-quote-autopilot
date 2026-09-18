QUOTE_EXTRACTION_SYSTEM_PROMPT = """
The provided document may contain:

- digital text
- scanned pages
- images
- tables
- logos
- signatures

Analyze the entire PDF visually.

Extract every supplier quotation present in the document.

Do not rely only on OCR text.

Use all visual information available.
""".strip()
