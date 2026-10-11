"""FoodEx2 sampMatCode -> EFSA food class -> Annex I commodity code (Regulation (EC) 396/2005).

A port of EFSA's SAS algorithm (applyMapping_CHEM_MON_2020, pesticide branch) to read the
rules and hierarchies extracted by rd_bridge.foodex2_mapping:

1. split the code into base term and explicit facets; add the base term's implicit facets,
   dropping whichever of an explicit/implicit pair of one category is the ancestor;
2. per category, take the ancestors of every facet code (each term's path includes itself);
3. walk the rules in order; a rule hits when each include facet is among those ancestors,
   no exclude facet is, and the code has at least as many facets of each category as the rule
   names. The first hit gives the food class, e.g. P0130050A -> Annex I code 0130050.

Usage: python -m rd_bridge.commodity <sampMatCode> [data/foodex2_ppp.json]
"""
import json
import re
import sys

FOOD_CLASS = re.compile(r"P(\d{7})(?:-(\d{3}))?([A-Z])")
COUNTED = ("F20", "F21", "F23", "F27", "F29")  # categories whose facet count a rule may require


class Classifier:
    def __init__(self, data: dict):
        self.rules = sorted(data["rules"], key=lambda r: r["order"])
        self.facet_hierarchy = data["facet_hierarchy"]
        self.parents = data["hierarchies"]
        self.reportable = {h: set(v) for h, v in data["reportable"].items()}
        self.implicit = data["implicit_facets"]
        self.base_hierarchies = {"MTX"} | {r["base_hierarchy"] for r in self.rules if r["base_hierarchy"]}
        for rule in self.rules:
            for facet in filter(None, f"{rule['include']}${rule['exclude']}".split("$")):
                header = facet.split(".")[0]
                if facet != "other" and header != "F00" and header not in self.facet_hierarchy:
                    raise ValueError(f"rule {rule['order']}: unsupported facet category {header}")

    @classmethod
    def load(cls, path: str = "data/foodex2_ppp.json") -> "Classifier":
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh))

    def path(self, term: str, hierarchy: str) -> list:
        """Ancestors of `term`, root first, ending with the term; [term] if it is not there."""
        parents = self.parents[hierarchy]
        if term not in parents:
            return [term]
        chain = []
        while term is not None:
            chain.append(term)
            term = parents.get(term)
        return chain[::-1]

    def _merge(self, explicit: list, implicit: list) -> list:
        merged = explicit + implicit
        for impl in implicit:
            for expl in explicit:
                ih, ic = impl.split(".")
                eh, ec = expl.split(".")
                if ih != eh or ic == ec or eh not in self.facet_hierarchy:
                    continue
                hierarchy = self.facet_hierarchy[eh]
                if ic in self.path(ec, hierarchy):
                    merged = [f for f in merged if f != impl]
                if ec in self.path(ic, hierarchy):
                    merged = [f for f in merged if f != expl]
        return list(dict.fromkeys(merged))

    def facets(self, code: str) -> tuple:
        code = code.strip().upper()
        base, _, explicit = code.partition("#")
        explicit = [f for f in explicit.split("$") if f]
        implicit = [f for f in self.implicit.get(base, "").split("$") if f]
        return base, self._merge(explicit, implicit)

    def classify(self, code: str) -> dict:
        base, merged = self.facets(code)
        by_header = {}
        for facet in merged:
            header, value = facet.split(".")
            by_header.setdefault(header, []).append(value)
        # SAS keeps one word list per category: ancestors of each facet code, joined
        words = {h: {w for v in by_header.get(h, []) for w in self.path(v, hier)}
                 for h, hier in self.facet_hierarchy.items()}
        count = {h: len(by_header.get(h, [])) for h in COUNTED}
        base_words = {h: set(self.path(base, h)) for h in self.base_hierarchies}

        def present(facet: str, hierarchy, include: bool) -> bool:
            header, value = facet.split(".")
            if header == "F00":
                if value == "ROOT":  # "base term reportable in the rule's hierarchy" (SAS: named ones only)
                    return hierarchy is not None and base in self.reportable.get(hierarchy, ())
                return value in base_words[hierarchy or "MTX"]
            if value == "ROOT":  # "any facet of this category"; SAS honours it only in includes
                return include and bool(by_header.get(header))
            return value in words[header]

        for rule in self.rules:
            hierarchy = rule["base_hierarchy"]
            include = [f for f in rule["include"].split("$") if f]
            exclude = [f for f in rule["exclude"].split("$") if f]
            if include == ["other"]:
                return self._result(code, base, merged, rule)
            needed = {h: sum(f.startswith(h + ".") for f in include) for h in COUNTED}
            if (all(present(f, hierarchy, True) for f in include)
                    and not any(present(f, hierarchy, False) for f in exclude)
                    and all(needed[h] <= count[h] for h in COUNTED)):
                return self._result(code, base, merged, rule)
        return self._result(code, base, merged, None)

    @staticmethod
    def _result(code: str, base: str, merged: list, rule) -> dict:
        food_class = rule["food_class"] if rule else None
        m = FOOD_CLASS.fullmatch(food_class or "")
        return {
            "sampMatCode": code,
            "base_term": base,
            "facets": merged,
            "food_class": food_class,
            # Annex I code the residue exceptions are keyed on; None for EFSA's special
            # classes (PX..., e.g. infant food) and for codes EFSA cannot classify (XXXXXXA)
            "annex_code": m.group(1) if m else None,
            "annex_subcode": m.group(2) if m and m.group(2) else None,
            "rule": {k: rule[k] for k in ("order", "base_hierarchy", "include", "exclude")} if rule else None,
        }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = sys.argv[2] if len(sys.argv) > 2 else "data/foodex2_ppp.json"
    print(json.dumps(Classifier.load(path).classify(sys.argv[1]), indent=1))


if __name__ == "__main__":
    main()
