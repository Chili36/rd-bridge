"""Download or import an EFSA PARAM catalogue without downgrading its version.

The public openefsa PARAM.ecf may lag behind the Catalogue Browser export.
Use a local Excel export to import a newer published catalogue:

    python -m rd_bridge.fetch_param PARAM_17.8.xlsx

With no argument, download openefsa's ECF only if it is at least as new as
the committed PARAM snapshot. Derived JSON is committed; raw archives are not.
"""
import json
import os
import sys
import tempfile

from rd_bridge import load_param
from rd_bridge.fetch_residues import download

URL = "https://raw.githubusercontent.com/openefsa/efsa-catalogues/master/ecf_catalogues/PARAM.ecf"


def version_tuple(value):
    try:
        return tuple(int(p) for p in str(value).split("."))
    except ValueError as exc:
        raise ValueError(f"Invalid PARAM catalogue version: {value!r}") from exc


def main() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        path = (sys.argv[1] if len(sys.argv) > 1 else
                download(URL, os.path.join(workdir, "PARAM.ecf")))
        incoming, _ = load_param.read_catalogue(path)
        if os.path.isfile("data/param_components.json"):
            with open("data/param_components.json", encoding="utf-8") as fh:
                committed = json.load(fh)["source"]["version"]
            if version_tuple(incoming["version"]) < version_tuple(committed):
                raise SystemExit(
                    f"Refusing PARAM downgrade: supplied {incoming['version']} is older "
                    f"than committed {committed}. Use the Catalogue Browser export "
                    f"or a newer authoritative ECF.")
        version, pest, comps = load_param.write(path)
    print(f"PARAM {version.get('version')} ({version.get('valid_from')}): {len(pest)} reportable "
          f"pestParam terms, {len(comps)} terms with families")


if __name__ == "__main__":
    main()
