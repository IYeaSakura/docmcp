"""
Generate test data files for DocMCP tests.

This script creates sample documents in various formats for testing purposes.
"""

import os
from pathlib import Path


def create_sample_pdf() -> bytes:
    """Create a minimal valid PDF file."""
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 5 0 R
>>
>>
>>
endobj
4 0 obj
<<
/Length 68
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Document for DocMCP) Tj
ET
endstream
endobj
5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000385 00000 n
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
463
%%EOF"""
    return pdf_content


def create_sample_docx() -> bytes:
    """Create a minimal DOCX file (ZIP archive with XML)."""
    try:
        import zipfile
        import io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # [Content_Types].xml
            content_types = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''
            zf.writestr('[Content_Types].xml', content_types)

            # _rels/.rels
            rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''
            zf.writestr('_rels/.rels', rels)

            # word/_rels/document.xml.rels
            doc_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>'''
            zf.writestr('word/_rels/document.xml.rels', doc_rels)

            # word/document.xml
            document = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
<w:p>
<w:r>
<w:t>Test DOCX Document for DocMCP</w:t>
</w:r>
</w:p>
<w:p>
<w:r>
<w:t>This is a sample paragraph for testing.</w:t>
</w:r>
</w:p>
<w:sectPr>
<w:pgSz w:w="12240" w:h="15840"/>
<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
</w:sectPr>
</w:body>
</w:document>'''
            zf.writestr('word/document.xml', document)

        return buffer.getvalue()
    except ImportError:
        # Fallback: return a placeholder
        return b"PK\x03\x04" + b"docx placeholder content"


def create_sample_xlsx() -> bytes:
    """Create a minimal XLSX file."""
    try:
        import zipfile
        import io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # [Content_Types].xml
            content_types = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''
            zf.writestr('[Content_Types].xml', content_types)

            # _rels/.rels
            rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
            zf.writestr('_rels/.rels', rels)

            # xl/workbook.xml
            workbook = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>
<sheet name="Sheet1" sheetId="1" r:id="rId1"/>
</sheets>
</workbook>'''
            zf.writestr('xl/workbook.xml', workbook)

            # xl/_rels/workbook.xml.rels
            wb_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''
            zf.writestr('xl/_rels/workbook.xml.rels', wb_rels)

            # xl/worksheets/sheet1.xml
            worksheet = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>
<row r="1">
<c r="A1" t="s"><v>Test XLSX</v></c>
<c r="B1" t="s"><v>Document</v></c>
</row>
<row r="2">
<c r="A2"><v>100</v></c>
<c r="B2"><v>200</v></c>
</row>
</sheetData>
</worksheet>'''
            zf.writestr('xl/worksheets/sheet1.xml', worksheet)

        return buffer.getvalue()
    except ImportError:
        return b"PK\x03\x04" + b"xlsx placeholder content"


def create_sample_pptx() -> bytes:
    """Create a minimal PPTX file."""
    try:
        import zipfile
        import io

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # [Content_Types].xml
            content_types = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>'''
            zf.writestr('[Content_Types].xml', content_types)

            # _rels/.rels
            rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>'''
            zf.writestr('_rels/.rels', rels)

            # ppt/presentation.xml
            presentation = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:sldIdLst>
<p:sldId id="256" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>
</p:sldIdLst>
</p:presentation>'''
            zf.writestr('ppt/presentation.xml', presentation)

            # ppt/_rels/presentation.xml.rels
            pres_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>'''
            zf.writestr('ppt/_rels/presentation.xml.rels', pres_rels)

            # ppt/slides/slide1.xml
            slide = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld>
<p:spTree>
<p:sp>
<p:txBody>
<a:bodyPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>
<a:lstStyle xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>
<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<a:r>
<a:t>Test PPTX Slide</a:t>
</a:r>
</a:p>
</p:txBody>
</p:sp>
</p:spTree>
</p:cSld>
</p:sld>'''
            zf.writestr('ppt/slides/slide1.xml', slide)

        return buffer.getvalue()
    except ImportError:
        return b"PK\x03\x04" + b"pptx placeholder content"


def create_sample_txt() -> bytes:
    """Create a sample text file."""
    content = """Test Text Document for DocMCP
================================

This is a sample text document for testing text extraction.

Section 1: Introduction
-----------------------
This document is used for testing the DocMCP document processing system.
It contains various text elements that can be extracted and analyzed.

Section 2: Features
-------------------
- Plain text support
- Multi-line content
- Special characters: @#$%^&*()
- Numbers: 12345, 3.14159
- Unicode: Hello World

Section 3: Conclusion
---------------------
This is the end of the test document.

Thank you for using DocMCP!
"""
    return content.encode('utf-8')


def create_sample_html() -> bytes:
    """Create a sample HTML file."""
    content = b"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Test HTML Document</title>
</head>
<body>
    <h1>Test HTML Document for DocMCP</h1>
    <p>This is a sample HTML document for testing.</p>
    <h2>Features</h2>
    <ul>
        <li>HTML parsing</li>
        <li>Text extraction</li>
        <li>Link detection</li>
    </ul>
    <p>Visit <a href="https://example.com">Example</a> for more info.</p>
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>Item1</td><td>100</td></tr>
        <tr><td>Item2</td><td>200</td></tr>
    </table>
</body>
</html>"""
    return content


def create_sample_md() -> bytes:
    """Create a sample Markdown file."""
    content = """# Test Markdown Document for DocMCP

## Introduction

This is a sample Markdown document for testing the DocMCP system.

## Features

- **Bold text** support
- *Italic text* support
- `Code` support

## Code Example

```python
def hello():
    print("Hello, DocMCP!")
```

## Links

Visit [DocMCP](https://example.com/docmcp) for more information.

## Table

| Name  | Value |
|-------|-------|
| Item1 | 100   |
| Item2 | 200   |

## Conclusion

This is the end of the test document.
"""
    return content.encode('utf-8')


def generate_all_test_data(output_dir: str = None) -> dict:
    """Generate all test data files.

    Args:
        output_dir: Directory to save files (default: same as script)

    Returns:
        Dictionary mapping filenames to content
    """
    if output_dir is None:
        output_dir = Path(__file__).parent
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    files = {
        'sample.pdf': create_sample_pdf(),
        'sample.docx': create_sample_docx(),
        'sample.xlsx': create_sample_xlsx(),
        'sample.pptx': create_sample_pptx(),
        'sample.txt': create_sample_txt(),
        'sample.html': create_sample_html(),
        'sample.md': create_sample_md(),
    }

    for filename, content in files.items():
        filepath = output_dir / filename
        with open(filepath, 'wb') as f:
            f.write(content)
        print(f"Created: {filepath}")

    return files


if __name__ == "__main__":
    generate_all_test_data()
