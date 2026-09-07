from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from prometeu.application.pipeline import ConversionPipeline
from prometeu.document.contracts import ConversionLimits, ConversionRequest, ConversionResult
from prometeu.document.model import (
    BoundingBox,
    Chapter,
    Heading,
    Inline,
    LineOrigin,
    Metadata,
    Paragraph,
    PhysicalDocument,
    PhysicalPage,
    SemanticDocument,
    SourceReference,
    TextStyle,
)


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_finite_limits(value):
    with pytest.raises(ValueError):
        ConversionLimits(timeout_seconds=value)


def test_coordinates_and_styles():
    with pytest.raises(ValueError):
        BoundingBox(1, 2, 0, 3)
    with pytest.raises(ValueError):
        BoundingBox(0, 0, float("nan"), 3)
    with pytest.raises(ValueError):
        TextStyle(size=0)
    box = BoundingBox(0, 0, 10, 10)
    with pytest.raises(FrozenInstanceError):
        box.x0 = 1


def test_one_based_consecutive_pages():
    with pytest.raises(ValueError):
        PhysicalPage(0, 100, 100, ())
    with pytest.raises(ValueError):
        PhysicalDocument("doc", (PhysicalPage(2, 100, 100, ()),))


def test_canonical_text_and_multipage_provenance():
    source = SourceReference((LineOrigin(1, "p1-l1"), LineOrigin(2, "p2-l1")))
    paragraph = Paragraph("para1", (Inline("ação — "), Inline("世界")), source)
    assert paragraph.text == "ação — 世界"
    assert {line.page for line in paragraph.source.lines} == {1, 2}


def test_single_chapter_title():
    heading = Heading("h1", 1, (Inline("Capítulo 1"),))
    with pytest.raises(ValueError):
        Chapter("c1", heading, (heading,))
    with pytest.raises(ValueError):
        SemanticDocument(
            "d",
            Metadata("Título", "urn:test"),
            (Chapter("c1", heading, (Paragraph("h1", (Inline("texto"),)),)),),
        )


def test_bootstrap_never_claims_success(tmp_path: Path):
    result = ConversionPipeline().run(ConversionRequest(tmp_path / "missing.pdf"))
    assert not result.success and result.exit_code != 0
    assert result.published_path is None
    with pytest.raises(ValueError):
        ConversionResult(success=True)
