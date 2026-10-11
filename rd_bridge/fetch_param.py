"""Download EFSA's PARAM catalogue and extract it (rd_bridge.load_param).

EFSA publishes the catalogue openly in github.com/openefsa/efsa-catalogues, updated every
few months; no account is needed. The .ecf itself is not committed.

Usage: python -m rd_bridge.fetch_param [PARAM.ecf]   (a local file skips the download)
"""
import os
import sys
import tempfile

from rd_bridge import load_param
from rd_bridge.fetch_residues import download

URL = "https://raw.githubusercontent.com/openefsa/efsa-catalogues/master/ecf_catalogues/PARAM.ecf"


def main() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        path = sys.argv[1] if len(sys.argv) > 1 else download(URL, os.path.join(workdir, "PARAM.ecf"))
        version, pest, comps = load_param.write(path)
    print(f"PARAM {version.get('version')} ({version.get('valid_from')}): {len(pest)} reportable "
          f"pestParam terms, {len(comps)} terms with families")


if __name__ == "__main__":
    main()
