"""PARAM Excel import contract and pinned 17.8 catalogue facts."""
import hashlib
import html
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from rd_bridge import fetch_param, load_param

ROOT = Path(__file__).resolve().parents[1]
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _sheet(rows):
    parts = [f'<worksheet xmlns="{MAIN}"><sheetData>']
    for ri, row in enumerate(rows, 1):
        parts.append(f'<row r="{ri}">')
        for ci, item in enumerate(row):
            col = chr(65 + ci)
            if item is not None:
                parts.append(f'<c r="{col}{ri}" t="inlineStr"><is><t>'
                             f'{html.escape(str(item))}</t></is></c>')
        parts.append('</row>')
    parts.append('</sheetData></worksheet>')
    return ''.join(parts)


class CatalogueBrowserXlsxTests(unittest.TestCase):
    def test_xlsx_import_uses_the_same_term_model_as_ecf(self):
        columns = ["termCode", "termExtendedName", "status", "deprecated", "pestClass",
                   "CAS", "otherNames", "commonNames", "masterFlag", "masterParentCode",
                   "masterReportable", "pestParamFlag", "pestParamParentCode", "pestParamReportable"]
        rows = [columns,
                ["RD-1", "Example sum", "APPROVED", "0", "RD", "", "", "", "1", "root", "1", "1", "RD-parent", "1"],
                ["C-1", "Example compound", "APPROVED", "0", "COMP", "123-45-6", "alias 1$alias 2", "", "1", "RD-1", "1", "1", "COMP-parent", "0"],
                ["OLD", "Old term", "DEPRECATED", "1", "AS", "", "", "", "1", "root", "1", "1", "RD-parent", "1"]]
        book = f'<workbook xmlns="{MAIN}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="catalogue" r:id="rId1"/><sheet name="term" r:id="rId2"/></sheets></workbook>'
        relations = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>'
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'PARAM.xlsx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('xl/workbook.xml', book)
                archive.writestr('xl/_rels/workbook.xml.rels', relations)
                archive.writestr('xl/worksheets/sheet1.xml', _sheet([
                    ['code', 'version', 'validFrom', 'status'],
                    ['PARAM', '17.8', '2026/09/11', 'PUBLISHED MINOR']]))
                archive.writestr('xl/worksheets/sheet2.xml', _sheet(rows))
            version, terms = load_param.read_catalogue(path)
            self.assertEqual((version['version'], version['valid_from']), ('17.8', '2026-09-11'))
            self.assertEqual(version['source_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(set(terms), {'RD-1', 'C-1'})
            self.assertEqual(terms['C-1']['attrs']['otherNames'], ['alias 1', 'alias 2'])
            self.assertEqual(load_param.pest_terms(terms)[0]['code'], 'RD-1')
            self.assertEqual(load_param.components(terms)['C-1']['param_parent'], 'RD-1')

    def test_pinned_param_17_8_source(self):
        data = json.loads((ROOT / 'data/param_components.json').read_text(encoding='utf-8'))
        self.assertEqual(data['source']['version'], '17.8')
        self.assertEqual(data['source']['valid_from'], '2026-09-11')
        self.assertEqual(data['source']['source_sha256'],
                         'bed02cc4e499474245f4899f17604880c1de00dd6e06df605dd3f27edf50b2fb')
        self.assertEqual(len(data['terms']), 2000)
        self.assertEqual(data['terms']['RF-00007587-PAR']['cas'], '143294-89-7')
        self.assertEqual(data['terms']['RF-00014619-PAR']['other_names'],
                         ['Distillates (petroleum), hydrotreated light paraffinic'])
        self.assertEqual(data['terms']['RF-0043-003-PPP']['cas'], '177406-68-7')
        pest = json.loads((ROOT / 'data/param_pest_terms.json').read_text(encoding='utf-8'))
        self.assertEqual(len(pest), 1391)

    def test_versions_are_compared_numerically(self):
        self.assertLess(fetch_param.version_tuple('17.8'), fetch_param.version_tuple('17.10'))


if __name__ == '__main__':
    unittest.main()
