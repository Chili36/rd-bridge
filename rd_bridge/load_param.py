"""Extract pesticide parameters from EFSA's PARAM catalogue (.ecf or .xlsx).

Writes two files:
- data/param_pest_terms.json: the approved, reportable pestParam terms that residue
  definitions are linked to (unchanged format);
- data/param_components.json: the catalogue version and every approved pestParam term,
  including the COMPONENTS group (metabolites and other parts of summed residues), with its
  names, CAS and its parent in PARAM's main hierarchy, where each substance heads a family
  of its summed terms and metabolites. Intermediate family nodes are kept too.

Usage: python -m rd_bridge.load_param <PARAM.ecf|PARAM.xlsx> [data/param_pest_terms.json] [data/param_components.json]
"""
import json
import sys
import zipfile
import xml.etree.ElementTree as ET

# Parent of pestParam terms that are not themselves reportable residues.
EXCLUDED_PARENT = "RF-00012999-PAR"


def read_catalogue(ecf_path: str) -> tuple:
    """Return (version info, {code: term}) for every approved term."""
    if str(ecf_path).lower().endswith(".xlsx"):
        from rd_bridge.load_param_xlsx import read_catalogue_xlsx
        return read_catalogue_xlsx(ecf_path)
    version, terms = {}, {}
    with zipfile.ZipFile(ecf_path) as zf:
        xml_name = next(n for n in zf.namelist() if n.endswith(".xml"))
        with zf.open(xml_name) as fh:
            for _, el in ET.iterparse(fh):
                if el.tag == "catalogueVersion" and not version:
                    version = {"version": el.findtext("version"), "valid_from": el.findtext("validFrom")}
                if el.tag != "term":
                    continue
                if el.findtext("termVersion/status") == "APPROVED":
                    hier = {h.findtext("hierarchyCode"): (h.findtext("reportable"), h.findtext("parentCode"))
                            for h in el.iter("hierarchyAssignment")}
                    attrs = {a.findtext("attributeCode"): [v.text for v in a.iter("attributeValue")]
                             for a in el.iter("implicitAttribute")}
                    terms[el.findtext("termDesc/termCode")] = {
                        "name": el.findtext("termDesc/termExtendedName"), "hier": hier, "attrs": attrs}
                el.clear()
    return version, terms


def pest_terms(terms: dict) -> list:
    out = []
    for code, t in sorted(terms.items()):
        pest = t["hier"].get("pestParam")
        if pest and pest[0] == "true" and pest[1] != EXCLUDED_PARENT:
            out.append({"code": code, "name": t["name"],
                        "pestClass": (t["attrs"].get("pestClass") or [None])[0],
                        "cas": (t["attrs"].get("CAS") or [None])[0]})
    return out


def components(terms: dict) -> dict:
    """Every approved pestParam term plus the PARAM-hierarchy nodes between it and its family."""
    keep = {c for c, t in terms.items() if "pestParam" in t["hier"]}
    for code in list(keep):
        node = terms[code]["hier"].get("PARAM", (None, None))[1]
        while node in terms and node not in keep:
            keep.add(node)
            node = terms[node]["hier"].get("PARAM", (None, None))[1]
    out = {}
    for code in sorted(keep):
        t = terms[code]
        pest = t["hier"].get("pestParam")
        entry = {"name": t["name"], "param_parent": t["hier"].get("PARAM", (None, None))[1]}
        if pest:
            entry["pest_parent"] = pest[1]
            entry["reportable"] = pest[0] == "true"
        for key, attr in (("pest_class", "pestClass"), ("cas", "CAS"),
                          ("other_names", "otherNames"), ("common_names", "commonNames")):
            if t["attrs"].get(attr):
                entry[key] = t["attrs"][attr] if key != "cas" else t["attrs"][attr][0]
        out[code] = entry
    return out


def write(ecf_path: str, terms_out: str = "data/param_pest_terms.json",
          components_out: str = "data/param_components.json") -> tuple:
    version, terms = read_catalogue(ecf_path)
    pest = pest_terms(terms)
    comps = components(terms)
    with open(terms_out, "w", encoding="utf-8") as fh:
        json.dump(pest, fh, ensure_ascii=False, indent=1)
    with open(components_out, "w", encoding="utf-8") as fh:
        json.dump({"source": {"catalogue": "PARAM", **version}, "terms": comps}, fh,
                  ensure_ascii=False, indent=1, sort_keys=True)
    return version, pest, comps


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    version, pest, comps = write(sys.argv[1], *sys.argv[2:4])
    print(f"PARAM {version.get('version')}: {len(pest)} reportable pestParam terms, "
          f"{len(comps)} terms with families")


if __name__ == "__main__":
    main()
