import time
from io import BytesIO

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)


pipeline_options = PdfPipelineOptions(
    do_ocr=False,
    do_table_structure=True,
    force_backend_text=True,
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
        )
    }
)


def parse_document(
    file_bytes: bytes,
    filename: str,
):
    stream = DocumentStream(
        name=filename,
        stream=BytesIO(file_bytes),
    )

    print("========== DOCLING START ==========")
    start = time.time()

    result = converter.convert(stream)

    print(
        f"========== DOCLING DONE: "
        f"{time.time() - start:.2f}s =========="
    )

    document = result.document

    markdown = document.export_to_markdown()

    return {
        "document": document,
        "markdown": markdown,
    }
