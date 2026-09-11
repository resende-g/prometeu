from __future__ import annotations

import posixpath
import re
import struct
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from prometeu.document.contracts import (
    ConversionLimits,
    Diagnostic,
    Severity,
    ValidationResult,
    ValidationStatus,
)

_CONTAINER = "META-INF/container.xml"
_MIMETYPE = b"application/epub+zip"
_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
_OPF_NS = "http://www.idpf.org/2007/opf"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_XHTML_NS = "http://www.w3.org/1999/xhtml"
_EPUB_NS = "http://www.idpf.org/2007/ops"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_MAX_ENTRIES = 10_000
_CHUNK_SIZE = 64 * 1024
_EXPECTED_CSS = b"h1, h2, h3 { break-after: avoid; }\n"
_MODIFIED = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z").fullmatch
_CONTENT_TAGS = {"html", "head", "title", "link", "body", "h1", "h2", "h3", "p", "strong", "em"}
_NAV_TAGS = {"html", "head", "title", "link", "body", "nav", "h1", "ol", "li", "a"}
_ATTRIBUTES = {
    "html": {"lang", f"{{{_XML_NS}}}lang"},
    "link": {"rel", "href"},
    "nav": {f"{{{_EPUB_NS}}}type"},
    "h1": {"id"},
    "h2": {"id"},
    "h3": {"id"},
    "p": {"id"},
    "a": {"href"},
}


class _InvalidEPUB(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InternalEPUBValidator:
    """Valida o perfil EPUB interno; não substitui o EPUBCheck."""

    def validate(self, path: Path, limits: ConversionLimits) -> ValidationResult:
        try:
            _validate(path, limits)
        except _InvalidEPUB as error:
            return _failed(error.code, str(error))
        except (OSError, EOFError, UnicodeError, ValueError, zipfile.BadZipFile):
            return _failed("EPUB_INVALID", "O arquivo não é um EPUB interno válido.")
        return ValidationResult("internal", ValidationStatus.PASSED)


def _failed(code: str, message: str) -> ValidationResult:
    return ValidationResult(
        "internal",
        ValidationStatus.FAILED,
        (Diagnostic(code, message, Severity.ERROR),),
    )


def _validate(path: Path, limits: ConversionLimits) -> None:
    if path.stat().st_size > limits.max_output_bytes:
        raise _InvalidEPUB("EPUB_SIZE_LIMIT", "EPUB excede o limite de saída.")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not infos or len(infos) > _MAX_ENTRIES:
            raise _InvalidEPUB("EPUB_ENTRY_LIMIT", "Quantidade de entradas ZIP inválida.")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise _InvalidEPUB("EPUB_DUPLICATE_ENTRY", "EPUB contém entradas ZIP duplicadas.")
        for info in infos:
            _validate_entry(info)
        if infos[0].filename != "mimetype" or infos[0].compress_type != zipfile.ZIP_STORED:
            raise _InvalidEPUB(
                "EPUB_MIMETYPE_ORDER",
                "mimetype deve ser a primeira entrada ZIP e não pode ser comprimida.",
            )
        _validate_mimetype_header(path, infos[0])
        declared_size = sum(info.file_size for info in infos)
        if declared_size > limits.max_output_bytes:
            raise _InvalidEPUB("EPUB_UNCOMPRESSED_LIMIT", "Conteúdo descomprimido excede o limite.")
        entries = _read_entries(archive, infos, limits.max_output_bytes)

    if entries.get("mimetype") != _MIMETYPE:
        raise _InvalidEPUB("EPUB_MIMETYPE_INVALID", "Conteúdo de mimetype inválido.")
    container = _parse_xml(entries, _CONTAINER)
    package_path = _package_path(container, entries)
    package = _parse_xml(entries, package_path)
    manifest, spine_paths, nav_path = _validate_package(package, package_path, entries)
    _validate_archive_members(entries, package_path, manifest)

    parsed_xhtml: dict[str, ET.Element] = {}
    for target, media_type in manifest.values():
        if media_type == "application/xhtml+xml":
            parsed_xhtml[target] = _parse_xml(entries, target)
    for target, root in parsed_xhtml.items():
        _validate_xhtml(root, target, target == nav_path, entries, manifest, parsed_xhtml)
    _validate_navigation(parsed_xhtml[nav_path], nav_path, spine_paths, entries, parsed_xhtml)
    _validate_css(entries, manifest)


def _validate_entry(info: zipfile.ZipInfo) -> None:
    if info.is_dir() or not _safe_archive_path(info.filename):
        raise _InvalidEPUB("EPUB_ENTRY_PATH", "EPUB contém caminho de entrada inseguro.")
    if info.flag_bits & 1:
        raise _InvalidEPUB("EPUB_ENCRYPTED_ENTRY", "EPUB contém entrada criptografada.")
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise _InvalidEPUB("EPUB_COMPRESSION_INVALID", "EPUB usa compressão não permitida.")
    mode = info.external_attr >> 16
    if mode & 0o170000 == 0o120000:
        raise _InvalidEPUB("EPUB_SYMLINK", "EPUB contém link simbólico.")


def _validate_mimetype_header(path: Path, info: zipfile.ZipInfo) -> None:
    if info.header_offset != 0 or info.extra:
        raise _InvalidEPUB("EPUB_MIMETYPE_HEADER", "Cabeçalho ZIP de mimetype inválido.")
    with path.open("rb") as source:
        header = source.read(30)
        if len(header) != 30:
            raise _InvalidEPUB("EPUB_MIMETYPE_HEADER", "Cabeçalho ZIP de mimetype inválido.")
        fields = struct.unpack("<4s5H3L2H", header)
        signature, flags, compression, name_size, extra_size = (
            fields[0],
            fields[2],
            fields[3],
            fields[9],
            fields[10],
        )
        name = source.read(name_size)
    if (
        signature != b"PK\x03\x04"
        or flags != 0
        or compression != zipfile.ZIP_STORED
        or name != b"mimetype"
        or extra_size != 0
    ):
        raise _InvalidEPUB("EPUB_MIMETYPE_HEADER", "Cabeçalho ZIP de mimetype inválido.")


def _safe_archive_path(name: str) -> bool:
    return bool(
        name
        and name == name.strip()
        and not name.startswith("/")
        and "\\" not in name
        and "%" not in name
        and all(part not in ("", ".", "..") for part in name.split("/"))
        and not any(ord(char) < 32 for char in name)
    )


def _read_entries(
    archive: zipfile.ZipFile, infos: list[zipfile.ZipInfo], limit: int
) -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    total = 0
    for info in infos:
        chunks: list[bytes] = []
        with archive.open(info) as source:
            while chunk := source.read(_CHUNK_SIZE):
                total += len(chunk)
                if total > limit:
                    raise _InvalidEPUB(
                        "EPUB_UNCOMPRESSED_LIMIT", "Conteúdo descomprimido excede o limite."
                    )
                chunks.append(chunk)
        entries[info.filename] = b"".join(chunks)
    return entries


def _parse_xml(entries: dict[str, bytes], name: str) -> ET.Element:
    data = entries.get(name)
    if data is None:
        raise _InvalidEPUB("EPUB_REQUIRED_ENTRY", "EPUB não contém arquivo obrigatório.")
    markup = data.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in markup or b"<!ENTITY" in markup:
        raise _InvalidEPUB("EPUB_XML_DECLARATION", "DTD e entidades são proibidas no EPUB.")
    try:
        return ET.fromstring(data)
    except (ET.ParseError, UnicodeError, ValueError) as error:
        raise _InvalidEPUB("EPUB_XML_INVALID", "EPUB contém XML inválido.") from error


def _package_path(container: ET.Element, entries: dict[str, bytes]) -> str:
    if (
        container.tag != f"{{{_CONTAINER_NS}}}container"
        or container.attrib != {"version": "1.0"}
        or [child.tag for child in container] != [f"{{{_CONTAINER_NS}}}rootfiles"]
    ):
        raise _InvalidEPUB("EPUB_CONTAINER_INVALID", "container.xml tem raiz inválida.")
    rootfiles = container.findall(f"./{{{_CONTAINER_NS}}}rootfiles/{{{_CONTAINER_NS}}}rootfile")
    wrapper = container[0]
    if len(rootfiles) != 1 or wrapper.attrib or list(wrapper) != rootfiles:
        raise _InvalidEPUB("EPUB_CONTAINER_INVALID", "container.xml deve indicar um pacote.")
    package_path = rootfiles[0].get("full-path", "")
    if (
        not _safe_archive_path(package_path)
        or package_path not in entries
        or rootfiles[0].get("media-type") != "application/oebps-package+xml"
        or set(rootfiles[0].attrib) != {"full-path", "media-type"}
        or list(rootfiles[0])
    ):
        raise _InvalidEPUB("EPUB_CONTAINER_INVALID", "Pacote indicado pelo container é inválido.")
    return package_path


def _validate_package(
    package: ET.Element, package_path: str, entries: dict[str, bytes]
) -> tuple[dict[str, tuple[str, str]], tuple[str, ...], str]:
    if (
        package.tag != f"{{{_OPF_NS}}}package"
        or package.get("version") != "3.0"
        or set(package.attrib) != {"version", "unique-identifier", f"{{{_XML_NS}}}lang"}
        or [child.tag for child in package]
        != [
            f"{{{_OPF_NS}}}metadata",
            f"{{{_OPF_NS}}}manifest",
            f"{{{_OPF_NS}}}spine",
        ]
    ):
        raise _InvalidEPUB("EPUB_PACKAGE_INVALID", "Pacote OPF não é EPUB 3.")
    metadata = package.find(f"{{{_OPF_NS}}}metadata")
    if metadata is None:
        raise _InvalidEPUB("EPUB_METADATA_INVALID", "Pacote não contém metadados.")
    identifier = _required_text(metadata, f"{{{_DC_NS}}}identifier")
    _required_text(metadata, f"{{{_DC_NS}}}title")
    language = _required_text(metadata, f"{{{_DC_NS}}}language")
    modified = [
        node
        for node in metadata.findall(f"{{{_OPF_NS}}}meta")
        if node.get("property") == "dcterms:modified" and (node.text or "").strip()
    ]
    allowed_metadata = {
        f"{{{_DC_NS}}}identifier",
        f"{{{_DC_NS}}}title",
        f"{{{_DC_NS}}}language",
        f"{{{_DC_NS}}}creator",
        f"{{{_OPF_NS}}}meta",
    }
    if any(node.tag not in allowed_metadata for node in metadata):
        raise _InvalidEPUB("EPUB_METADATA_INVALID", "Metadados fora do perfil interno.")
    creators = metadata.findall(f"{{{_DC_NS}}}creator")
    if len(creators) > 1 or (creators and not (creators[0].text or "").strip()):
        raise _InvalidEPUB("EPUB_METADATA_INVALID", "Autoria do pacote é inválida.")
    expected_metadata = [
        f"{{{_DC_NS}}}identifier",
        f"{{{_DC_NS}}}title",
        f"{{{_DC_NS}}}language",
        *([f"{{{_DC_NS}}}creator"] if creators else []),
        f"{{{_OPF_NS}}}meta",
    ]
    if [node.tag for node in metadata] != expected_metadata:
        raise _InvalidEPUB("EPUB_METADATA_INVALID", "Metadados fora do perfil interno.")
    for node in metadata:
        allowed_attributes = (
            {"id"}
            if node.tag == f"{{{_DC_NS}}}identifier"
            else {"property"}
            if node.tag == f"{{{_OPF_NS}}}meta"
            else set()
        )
        if set(node.attrib) != allowed_attributes or list(node):
            raise _InvalidEPUB("EPUB_METADATA_INVALID", "Metadados fora do perfil interno.")
    modified_text = (modified[0].text or "").strip() if len(modified) == 1 else ""
    try:
        if not _MODIFIED(modified_text):
            raise ValueError
        datetime.strptime(modified_text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise _InvalidEPUB(
            "EPUB_METADATA_INVALID", "Data de modificação do pacote é inválida."
        ) from error
    identifier_id = identifier.get("id", "")
    if (
        not identifier_id
        or package.get("unique-identifier") != identifier_id
        or package.get(f"{{{_XML_NS}}}lang") != (language.text or "").strip()
    ):
        raise _InvalidEPUB("EPUB_METADATA_INVALID", "Metadados mínimos do pacote são inválidos.")

    manifest_node = package.find(f"{{{_OPF_NS}}}manifest")
    spine_node = package.find(f"{{{_OPF_NS}}}spine")
    if manifest_node is None or spine_node is None:
        raise _InvalidEPUB("EPUB_PACKAGE_INVALID", "Manifest ou spine ausente.")
    if manifest_node.attrib or any(node.tag != f"{{{_OPF_NS}}}item" for node in manifest_node):
        raise _InvalidEPUB("EPUB_MANIFEST_INVALID", "Manifest contém estrutura inválida.")
    if spine_node.attrib or any(node.tag != f"{{{_OPF_NS}}}itemref" for node in spine_node):
        raise _InvalidEPUB("EPUB_SPINE_INVALID", "Spine contém estrutura inválida.")
    manifest: dict[str, tuple[str, str]] = {}
    targets: set[str] = set()
    nav_paths: list[str] = []
    for item in manifest_node.findall(f"{{{_OPF_NS}}}item"):
        item_id = item.get("id", "")
        media_type = item.get("media-type", "")
        target, fragment = _resolve_reference(package_path, item.get("href", ""), entries)
        if (
            not item_id
            or media_type not in ("application/xhtml+xml", "text/css")
            or fragment
            or item_id in manifest
            or target in targets
        ):
            raise _InvalidEPUB(
                "EPUB_MANIFEST_INVALID", "Manifest contém item inválido ou duplicado."
            )
        manifest[item_id] = (target, media_type)
        targets.add(target)
        properties = item.get("properties", "")
        expected_attributes = {"id", "href", "media-type"} | (
            {"properties"} if properties else set()
        )
        if set(item.attrib) != expected_attributes or list(item):
            raise _InvalidEPUB("EPUB_MANIFEST_INVALID", "Manifest contém item inválido.")
        if properties == "nav":
            nav_paths.append(target)
            if media_type != "application/xhtml+xml":
                raise _InvalidEPUB("EPUB_NAV_INVALID", "Documento de navegação não é XHTML.")
        elif properties:
            raise _InvalidEPUB("EPUB_MANIFEST_INVALID", "Manifest contém propriedade inválida.")
    if len(nav_paths) != 1:
        raise _InvalidEPUB("EPUB_NAV_INVALID", "Manifest deve declarar uma navegação.")

    spine_paths: list[str] = []
    for itemref in spine_node.findall(f"{{{_OPF_NS}}}itemref"):
        if set(itemref.attrib) != {"idref"} or list(itemref):
            raise _InvalidEPUB("EPUB_SPINE_INVALID", "Spine contém item inválido.")
        spine_item = manifest.get(itemref.get("idref", ""))
        if (
            spine_item is None
            or spine_item[1] != "application/xhtml+xml"
            or spine_item[0] in spine_paths
        ):
            raise _InvalidEPUB("EPUB_SPINE_INVALID", "Spine referencia item inválido.")
        spine_paths.append(spine_item[0])
    if not spine_paths:
        raise _InvalidEPUB("EPUB_SPINE_INVALID", "Spine não contém capítulos.")
    if nav_paths[0] in spine_paths:
        raise _InvalidEPUB("EPUB_SPINE_INVALID", "Navegação não pode compor o spine.")
    return manifest, tuple(spine_paths), nav_paths[0]


def _required_text(parent: ET.Element, tag: str) -> ET.Element:
    nodes = parent.findall(tag)
    if len(nodes) != 1 or not (nodes[0].text or "").strip():
        raise _InvalidEPUB("EPUB_METADATA_INVALID", "Metadado obrigatório ausente ou duplicado.")
    return nodes[0]


def _resolve_reference(source: str, reference: str, entries: dict[str, bytes]) -> tuple[str, str]:
    if (
        not reference
        or reference != reference.strip()
        or "\\" in reference
        or "%" in reference
        or any(ord(char) < 32 for char in reference)
    ):
        raise _InvalidEPUB("EPUB_LINK_UNSAFE", "EPUB contém referência insegura.")
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or parsed.query:
        raise _InvalidEPUB("EPUB_LINK_UNSAFE", "EPUB contém referência externa ou insegura.")
    relative = parsed.path
    if relative.startswith("/"):
        raise _InvalidEPUB("EPUB_LINK_UNSAFE", "EPUB contém referência externa ou insegura.")
    target = (
        source
        if not relative
        else posixpath.normpath(posixpath.join(posixpath.dirname(source), relative))
    )
    if not _safe_archive_path(target) or target not in entries:
        raise _InvalidEPUB("EPUB_LINK_UNSAFE", "EPUB contém referência ausente ou insegura.")
    return target, parsed.fragment


def _validate_archive_members(
    entries: dict[str, bytes], package_path: str, manifest: dict[str, tuple[str, str]]
) -> None:
    declared = {target for target, _ in manifest.values()}
    allowed = {"mimetype", _CONTAINER, package_path, *declared}
    if set(entries) != allowed:
        raise _InvalidEPUB("EPUB_UNDECLARED_ENTRY", "EPUB contém arquivo não declarado.")


def _validate_xhtml(
    root: ET.Element,
    source: str,
    is_navigation: bool,
    entries: dict[str, bytes],
    manifest: dict[str, tuple[str, str]],
    parsed_xhtml: dict[str, ET.Element],
) -> None:
    if root.tag != f"{{{_XHTML_NS}}}html":
        raise _InvalidEPUB("EPUB_XHTML_INVALID", "Documento XHTML tem raiz inválida.")
    children = list(root)
    if [child.tag for child in children] != [
        f"{{{_XHTML_NS}}}head",
        f"{{{_XHTML_NS}}}body",
    ]:
        raise _InvalidEPUB("EPUB_XHTML_INVALID", "Documento XHTML exige head e body.")
    head, body = children
    if [child.tag for child in head] != [
        f"{{{_XHTML_NS}}}title",
        f"{{{_XHTML_NS}}}link",
    ] or not (head[0].text or "").strip():
        raise _InvalidEPUB("EPUB_XHTML_INVALID", "Head XHTML é inválido.")
    stylesheet = head[1].get("href", "")
    if head[1].get("rel") != "stylesheet" or list(head[0]) or list(head[1]) or not stylesheet:
        raise _InvalidEPUB("EPUB_XHTML_INVALID", "Folha de estilo XHTML é inválida.")
    stylesheet_target, stylesheet_fragment = _resolve_reference(source, stylesheet, entries)
    if stylesheet_fragment or (stylesheet_target, "text/css") not in manifest.values():
        raise _InvalidEPUB("EPUB_XHTML_INVALID", "Folha de estilo XHTML é inválida.")
    language = root.get("lang", "")
    if not language or root.get(f"{{{_XML_NS}}}lang") != language:
        raise _InvalidEPUB("EPUB_XHTML_INVALID", "Idioma XHTML é inválido.")
    for element in root.iter():
        name = _local_name(element.tag).casefold()
        if name == "script" or any(
            _local_name(attribute).casefold().startswith("on") for attribute in element.attrib
        ):
            raise _InvalidEPUB("EPUB_ACTIVE_CONTENT", "Conteúdo ativo é proibido no EPUB.")
        for attribute, value in element.attrib.items():
            if _local_name(attribute).casefold() in {"href", "src"}:
                _resolve_reference(source, value, entries)

    if is_navigation:
        if [child.tag for child in body] != [f"{{{_XHTML_NS}}}nav"]:
            raise _InvalidEPUB("EPUB_NAV_INVALID", "Body da navegação é inválido.")
    elif any(
        child.tag
        not in {
            f"{{{_XHTML_NS}}}h1",
            f"{{{_XHTML_NS}}}h2",
            f"{{{_XHTML_NS}}}h3",
            f"{{{_XHTML_NS}}}p",
        }
        for child in body
    ):
        raise _InvalidEPUB("EPUB_XHTML_PROFILE", "Capítulo contém estrutura não gerada.")
    elif any(not _valid_block(block) for block in body):
        raise _InvalidEPUB(
            "EPUB_XHTML_PROFILE", "Markup do capítulo não pertence ao perfil interno."
        )

    declared = {target for target, _ in manifest.values()}
    allowed_tags = _NAV_TAGS if is_navigation else _CONTENT_TAGS
    ids: set[str] = set()
    for element in root.iter():
        name = _local_name(element.tag).casefold()
        if (
            element.tag != f"{{{_XHTML_NS}}}{name}"
            or name not in allowed_tags
            or set(element.attrib) - _ATTRIBUTES.get(name, set())
        ):
            raise _InvalidEPUB(
                "EPUB_ACTIVE_CONTENT", "Elemento ou atributo ativo/não permitido no EPUB."
            )
        element_id = element.get("id")
        if element_id is not None:
            if not element_id or element_id in ids:
                raise _InvalidEPUB("EPUB_ANCHOR_INVALID", "XHTML contém âncora inválida.")
            ids.add(element_id)
        reference = element.get("href")
        if reference is None:
            continue
        target, fragment = _resolve_reference(source, reference, entries)
        if target not in declared:
            raise _InvalidEPUB("EPUB_LINK_UNDECLARED", "Referência aponta para item não declarado.")
        if fragment:
            target_root = parsed_xhtml.get(target)
            if target_root is None or fragment not in _ids(target_root):
                raise _InvalidEPUB("EPUB_ANCHOR_INVALID", "Referência aponta para âncora ausente.")
    if not is_navigation and any(not child.get("id") for child in body):
        raise _InvalidEPUB("EPUB_ANCHOR_INVALID", "Bloco do capítulo não possui âncora.")


def _valid_block(block: ET.Element) -> bool:
    for child in block:
        name = _local_name(child.tag)
        if name not in {"strong", "em"}:
            return False
        if name == "em" and list(child):
            return False
        if name == "strong" and any(_local_name(grandchild.tag) != "em" for grandchild in child):
            return False
        if name == "strong" and any(list(grandchild) for grandchild in child):
            return False
    return True


def _validate_navigation(
    root: ET.Element,
    source: str,
    spine_paths: tuple[str, ...],
    entries: dict[str, bytes],
    parsed_xhtml: dict[str, ET.Element],
) -> None:
    toc = [
        node
        for node in root.iter(f"{{{_XHTML_NS}}}nav")
        if node.get(f"{{{_EPUB_NS}}}type") == "toc"
    ]
    if len(toc) != 1:
        raise _InvalidEPUB("EPUB_NAV_INVALID", "Navegação deve conter um índice.")
    if [child.tag for child in toc[0]] != [
        f"{{{_XHTML_NS}}}h1",
        f"{{{_XHTML_NS}}}ol",
    ] or not (toc[0][0].text or "").strip():
        raise _InvalidEPUB("EPUB_NAV_INVALID", "Estrutura da navegação é inválida.")
    for listing in toc[0].iter(f"{{{_XHTML_NS}}}ol"):
        if not list(listing) or any(child.tag != f"{{{_XHTML_NS}}}li" for child in listing):
            raise _InvalidEPUB("EPUB_NAV_INVALID", "Navegação contém lista vazia.")
    for item in toc[0].iter(f"{{{_XHTML_NS}}}li"):
        tags = [child.tag for child in item]
        if tags not in (
            [f"{{{_XHTML_NS}}}a"],
            [f"{{{_XHTML_NS}}}a", f"{{{_XHTML_NS}}}ol"],
        ) or list(item[0]):
            raise _InvalidEPUB("EPUB_NAV_INVALID", "Navegação contém item sem link.")
    links = list(toc[0].iter(f"{{{_XHTML_NS}}}a"))
    if not links:
        raise _InvalidEPUB("EPUB_NAV_INVALID", "Navegação não contém capítulos.")
    linked_spine: list[str] = []
    for link in links:
        if not "".join(link.itertext()).strip():
            raise _InvalidEPUB("EPUB_NAV_INVALID", "Navegação contém link sem texto.")
        target, fragment = _resolve_reference(source, link.get("href", ""), entries)
        if target not in spine_paths:
            raise _InvalidEPUB("EPUB_NAV_INVALID", "Navegação aponta fora do spine.")
        if not linked_spine or linked_spine[-1] != target:
            linked_spine.append(target)
        if fragment and fragment not in _ids(parsed_xhtml[target]):
            raise _InvalidEPUB("EPUB_ANCHOR_INVALID", "Navegação aponta para âncora ausente.")
    if tuple(linked_spine) != spine_paths:
        raise _InvalidEPUB("EPUB_NAV_INVALID", "Navegação não cobre o spine em ordem.")


def _validate_css(entries: dict[str, bytes], manifest: dict[str, tuple[str, str]]) -> None:
    for target, media_type in manifest.values():
        if media_type != "text/css":
            continue
        if entries[target] != _EXPECTED_CSS:
            raise _InvalidEPUB(
                "EPUB_CSS_INVALID", "Folha de estilo não pertence ao perfil interno."
            )


def _ids(root: ET.Element) -> set[str]:
    return {value for element in root.iter() if (value := element.get("id"))}


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1]
