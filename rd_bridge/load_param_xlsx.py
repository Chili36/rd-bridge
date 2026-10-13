"""Read EFSA Catalogue Browser's PARAM Excel export into the ECF term model.

The term sheet expands to hundreds of MB of XML. Read only the needed cells,
without materialising an XML element tree for every catalogue hierarchy.
No third-party spreadsheet dependency is required.
"""
import hashlib
import html
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_ROWS = re.compile(rb'<row\\b[^>]*>(.*?)</row>', re.DOTALL)
_CELLS = re.compile(rb'<c\\s+r="([A-Z]+)\\d+"[^>]*>(.*?)</c>', re.DOTALL)
_VALUES = re.compile(rb'<(?:t(?:\\s+[^>]*)?|v)>(.*?)</(?:t|v)>', re.DOTALL)
_TERMS = {
    "termCode", "termExtendedName", "status", "deprecated", "pestClass",
    "CAS", "otherNames", "commonNames", "masterFlag", "masterParentCode",
    "masterReportable", "pestParamFlag", "pestParamParentCode", "pestParamReportable",
}


def _sheet_paths(archive: zipfile.ZipFile) -> dict:
    book = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels.iter(_PKG_REL + "Relationship")}
    paths = {}
    for sheet in book.iter(_MAIN + "sheet"):
        name, rel = sheet.get("name"), sheet.get(_REL + "id")
        target = targets.get(rel)
        if target:
            paths[name] = (target.lstrip("/") if target.startswith("/") else
                           posixpath.normpath(posixpath.join("xl", target)))
    if "catalogue" not in paths or "term" not in paths:
        raise ValueError("Expected EFSA PARAM Excel sheets 'catalogue' and 'term'")
    return paths


def _rows(archive: zipfile.ZipFile, path: str, wanted: set):
    # The current EFSA export uses inline strings. Reject a changed encoding
    # rather than accidentally treating a shared-string index as a term code.
    contents = archive.read(path)
    columns = None
    for row in _ROWS.finditer(contents):
        cells = {}
        for match in _CELLS.finditer(row.group(1)):
            col, cell = match.groups()
            col = col.decode("ascii")
            if columns is not None and col not in columns:
                continue
            if b't="s"' in match.group(0)[:80]:
                raise ValueError("Shared strings unsupported; use an EFSA Catalogue Browser export")
            parts = _VALUES.findall(cell)
            if parts:
                cells[col] = html.unescape(b"".join(parts).decode("utf-8"))
        if columns is None:
            columns = {col: name for col, name in cells.items() if name in wanted}
            if not wanted.issubset(set(columns.values())):
                raise ValueError("EFSA PARAM Excel export missing required columns: " +
                                 ", ".join(sorted(wanted - set(columns.values()))))
        else:
            yield {name: cells.get(col) for col, name in columns.items()}


def _flag(value) -> bool:
    return str(value or "").lower() in ("1", "true")


def _values(value) -> list:
    # Repeatable attributes use '$'. Preserve whitespace as in ECF exports.
    return [s for s in (value or "").split("$") if s]


def read_catalogue_xlsx(path) -> tuple:
    """Return (version metadata, approved code-to-term index), like ECF."""
    with zipfile.ZipFile(path) as archive:
        paths = _sheet_paths(archive)
        metadata = next(_rows(archive, paths["catalogue"],
                              {"code", "version", "validFrom", "status"}), None)
        if not metadata or metadata["code"] != "PARAM":
            raise ValueError("Not an EFSA PARAM catalogue workbook")
        if not metadata["version"] or metadata["status"] not in ("PUBLISHED MINOR", "PUBLISHED MAJOR"):
            raise ValueError("EFSA PARAM catalogue version is not published")
        with open(path, "rb") as fh:
            checksum = hashlib.sha256(fh.read()).hexdigest()
        version = {
            "version": metadata["version"],
            "valid_from": (metadata["validFrom"] or "").replace("/", "-"),
            "source_format": "EFSA Catalogue Browser XLSX",
            "source_sha256": checksum,
        }
        terms = {}
        for row in _rows(archive, paths["term"], _TERMS):
            if row["status"] != "APPROVED" or _flag(row["deprecated"]):
                continue
            code = row["termCode"]
            if not code:
                raise ValueError("Approved PARAM term with missing code")
            hier = {}
            if _flag(row["masterFlag"]):
                hier["PARAM"] = ("true" if _flag(row["masterReportable"]) else "false",
                                 row["masterParentCode"])
            if _flag(row["pestParamFlag"]):
                hier["pestParam"] = ("true" if _flag(row["pestParamReportable"]) else "false",
                                     row["pestParamParentCode"])
            attrs = {key: values for key in ("pestClass", "CAS", "otherNames", "commonNames")
                     if (values := _values(row[key]))}
            terms[code] = {"name": row["termExtendedName"], "hier": hier, "attrs": attrs}
        if not terms:
            raise ValueError("No approved terms in EFSA PARAM Excel export")
        return version, terms
