import re
from statistics import median

from prometeu.cleaning.normalize import xml_text_valid
from prometeu.document.contracts import ConversionRequest, Diagnostic, InputError
from prometeu.document.model import Metadata, PDFMetadata, PhysicalDocument


def resolve_metadata(
    request: ConversionRequest,
    pdf: PDFMetadata,
    digest: str,
    physical: PhysicalDocument | None = None,
) -> tuple[Metadata, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []

    def choose(
        override: str | None, candidate: str | None, field: str, max_length: int = 512
    ) -> str | None:
        def valid(value: str) -> bool:
            return (
                0 < len(value.strip()) <= max_length
                and xml_text_valid(value)
                and not any(ord(c) < 32 or 0x7F <= ord(c) <= 0x9F for c in value)
            )

        if override is not None:
            if not valid(override):
                raise InputError("METADATA_INVALID", f"Override de {field} inválido.")
            return override.strip()
        if candidate is not None:
            if valid(candidate):
                return candidate.strip()
            diagnostics.append(
                Diagnostic("METADATA_IGNORED", f"Metadado {field} inválido ignorado.")
            )
        return None

    title = choose(request.title, pdf.title, "título")
    if title is None and physical and physical.pages:
        lines = [line for line in physical.pages[0].lines if line.text.strip()]
        sizes = [span.style.size for line in lines[1:] for span in line.spans]
        if lines and sizes:
            first = lines[0]
            candidate = first.text.strip()
            if (
                4 <= len(candidate) <= 160
                and not candidate.endswith((".", "!", "?", ";"))
                and first.bbox.top < physical.pages[0].height * 0.3
                and first.spans
                and min(span.style.size for span in first.spans) > median(sizes) * 1.3
            ):
                title = choose(None, candidate, "título inferido")
                if title:
                    diagnostics.append(
                        Diagnostic("TITLE_INFERRED", "Título inferido da primeira linha destacada.")
                    )
    if title is None:
        title = "Documento sem título"
        diagnostics.append(
            Diagnostic("TITLE_UNKNOWN", "Título não disponível; usado título genérico.")
        )
    author = choose(request.author, pdf.author, "autor")
    language = choose(request.language, pdf.language, "idioma", 63)
    if language and not re.fullmatch(
        r"(?:[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{1,8})*|x(?:-[a-zA-Z0-9]{1,8})+)", language
    ):
        if request.language is not None:
            raise InputError(
                "LANGUAGE_INVALID", "Idioma deve ter sintaxe BCP 47, como pt-BR ou und."
            )
        language = None
    if language is None:
        language = "und"
        diagnostics.append(Diagnostic("LANGUAGE_UNKNOWN", "Idioma indeterminado: und."))
    identifier = choose(request.identifier, None, "identificador", 1024) or f"urn:sha256:{digest}"
    return Metadata(title, identifier, language, author), tuple(diagnostics)
