"""
Public-record facts for the famous-figure models and Elon, from Wikidata (CC0).

For each figure in figures/sources.json ("wikidata" id), and the people in
ALSO, this writes models/<id>/profile.json with
  - "facts":   short label -> value lines for the AI voice's prompt
  - "answers": first-person sentences for quick profile questions
               ("Which year were you born, and where?"), see services/profile.py
  - "aliases": other names people use for them ("Bapu", "Musk"), so
               "How many kids does Elon Musk have?" counts as asking them
Family (parents, siblings, marriages, partners, children, grandchildren,
relatives), net worth (latest and highest, with dates), height, religion,
offices, death and burial: anything published about a public figure is
answered, never treated as private. These are public records about the
person, not their own words, and the chat labels them that way. Re-run to
refresh (net worth and family change); edit figures/profile_overrides.json
to correct.

    python figures/fetch_profiles.py [--only mahatma_gandhi]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "CHRONUS-research/0.1 (university research project; profile facts for public figures)"}
GREGORIAN = "http://www.wikidata.org/entity/Q1985727"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
# People with a profile whose models are not built from figures/sources.json
ALSO = [{"id": "elon_musk", "name": "Elon Musk", "wikidata": "Q317521"}]
LINKED = ("P19", "P20", "P22", "P25", "P3373", "P26", "P451", "P40", "P1038", "P69", "P106", "P27", "P166", "P800",
          "P140", "P39", "P102", "P509", "P119", "P1412")
USD = "http://www.wikidata.org/entity/Q4917"
METRES = {"http://www.wikidata.org/entity/Q11573": 1.0, "http://www.wikidata.org/entity/Q174728": 0.01}


def get_entities(ids: list[str], props: str) -> dict:
    entities = {}
    for start in range(0, len(ids), 50):
        params = {"action": "wbgetentities", "ids": "|".join(ids[start:start + 50]), "props": props,
                  "languages": "en|mul", "format": "json"}
        for attempt in range(6):
            r = requests.get(API, params=params, headers=HEADERS, timeout=60)
            if r.status_code not in (429, 503):
                break
            time.sleep(int(r.headers.get("Retry-After", "0") or 0) or 5 * (attempt + 1))  # Wikidata rate limit
        r.raise_for_status()
        entities.update(r.json()["entities"])
        time.sleep(1)  # be polite to the public API
    return entities


def label_of(entity: dict) -> str | None:
    """English label, else the language-neutral "mul" label Wikidata now uses for many names."""
    labels = entity.get("labels", {})
    return (labels.get("en") or labels.get("mul") or {}).get("value")


def statements(entity: dict, pid: str) -> list[dict]:
    """Usable statements, preferred-rank ones only when the property has any."""
    claims = [c for c in entity.get("claims", {}).get(pid, [])
              if c["rank"] != "deprecated" and c["mainsnak"]["snaktype"] == "value"]
    return [c for c in claims if c["rank"] == "preferred"] or claims


def qualifier_time(claim: dict, pid: str) -> str:
    for q in claim.get("qualifiers", {}).get(pid, []):
        if q["snaktype"] == "value":
            return q["datavalue"]["value"]["time"]
    return ""


def qualifier_ids(claim: dict, pid: str) -> list[str]:
    return [q["datavalue"]["value"]["id"] for q in claim.get("qualifiers", {}).get(pid, []) if q["snaktype"] == "value"]


def item_ids(entity: dict, pid: str) -> list[str]:
    return [c["mainsnak"]["datavalue"]["value"]["id"] for c in statements(entity, pid)]


def best_date(entity: dict, pid: str) -> dict | None:
    """The most precise date, Gregorian calendar first: {"text", "year", "date"}."""
    values = [c["mainsnak"]["datavalue"]["value"] for c in statements(entity, pid)]
    if not values:
        return None
    v = max(values, key=lambda v: (v["precision"], v.get("calendarmodel") == GREGORIAN))
    sign, rest = v["time"][0], v["time"][1:]
    year, month, day = (int(x) for x in rest[:10].split("-"))
    year = -year if sign == "-" else year
    if v["precision"] >= 11:
        return {"text": f"{day} {MONTHS[month - 1]} {year}", "year": year, "date": date(year, month, day)}
    if v["precision"] == 10:
        return {"text": f"{MONTHS[month - 1]} {year}", "year": year, "date": None}
    return {"text": str(year), "year": year, "date": None}


def time_text(stamp: str) -> str:
    """'+2026-06-12T00:00:00Z' -> '12 June 2026' (or 'June 2026', '2026')."""
    year, month, day = (int(x) for x in stamp[1:11].split("-"))
    return f"{day} {MONTHS[month - 1]} {year}" if day else f"{MONTHS[month - 1]} {year}" if month else str(year)


def year_of(stamp: str) -> int | None:
    return int(stamp[1:5]) if stamp else None


def join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def money(amount: float) -> str:
    if amount >= 1e9:
        return f"${amount / 1e9:,.0f} billion" if amount >= 1e10 else f"${amount / 1e9:,.1f} billion"
    return f"${amount / 1e6:,.0f} million"


def _family(person: dict, labels: dict, children: dict, own_id: str, surname: str, died: dict | None) -> tuple[dict, dict]:
    """Siblings, marriages, partners, children, grandchildren and relatives: (facts, answers)."""
    alive = died is None
    facts, answers = {}, {}

    def name(qid: str) -> str:
        return (labels.get(qid, {}).get("label") or "").rstrip(".")

    def kin_named(pid: str) -> list[str]:
        out = []
        for c in statements(person, pid):
            n = name(c["mainsnak"]["datavalue"]["value"]["id"])
            kin = [name(k) for k in qualifier_ids(c, "P1039") if name(k)]
            n = f"{n} ({kin[0]})" if n and kin else n
            if n and n.lower() not in (o.lower() for o in out):
                out.append(n)
        return out

    siblings = kin_named("P3373")
    if siblings:
        facts["Siblings"] = join(siblings)
        answers["siblings"] = (f"I {'have' if alive else 'had'} one sibling, {siblings[0]}." if len(siblings) == 1 else
                               f"I {'have' if alive else 'had'} {len(siblings)} siblings: {join(siblings)}.")

    marriages = []
    for c in sorted(statements(person, "P26"), key=lambda c: qualifier_time(c, "P580") or "+9999"):
        m = (name(c["mainsnak"]["datavalue"]["value"]["id"]), year_of(qualifier_time(c, "P580")), year_of(qualifier_time(c, "P582")))
        if m[0] and m not in marriages:
            marriages.append(m)
    if marriages:
        def span(m):
            return f" ({m[1]}–{m[2]})" if m[1] and m[2] else f" (from {m[1]})" if m[1] else ""
        facts["Spouse"] = "; ".join(m[0] + span(m) for m in marriages)
        by_person = {}
        for m in marriages:
            by_person.setdefault(m[0], []).append(m)
        parts = [(f"twice to {who}" if len(ms) == 2 else f"to {who}") +
                 (f" ({', '.join(span(m).strip(' ()') for m in ms)})" if alive and any(span(m) for m in ms) else "")
                 for who, ms in by_person.items()]
        times = {1: "once", 2: "twice", 3: "three times"}.get(len(marriages), f"{len(marriages)} times")
        current = [m for m in marriages if m[1] and not m[2]] if alive else []
        if len(marriages) == 1:
            m = marriages[0]
            answers["spouse"] = (f"I'm married to {m[0]}." if current else
                                 f"I was married to {m[0]}" + (span(m) if alive else "") + ".")
        else:
            answers["spouse"] = (f"I've been married {times}: {join(parts)}." if alive else
                                 f"I was married {times}: first {parts[0]}, then {join(parts[1:])}.")

    partners = [p for p in kin_named("P451") if p not in by_person] if marriages else kin_named("P451")
    if partners:
        facts["Partners"] = join(partners)
        answers["partners"] = f"My partners {'have included' if alive else 'included'} {join(partners)}."

    kids = []
    for c in statements(person, "P40"):
        cid = c["mainsnak"]["datavalue"]["value"]["id"]
        label = name(cid)
        if not label or any(k["name"].lower() == label.lower() for k in kids):
            continue
        child = children.get(cid, {})
        short = label[: -len(surname) - 1] if surname and label.endswith(" " + surname) else label
        born, gone = best_date(child, "P569"), best_date(child, "P570")
        if gone and (alive or gone["year"] < died["year"]):
            short += f" (died {gone['year']})"
        other = next((name(p) for p in item_ids(child, "P22") + item_ids(child, "P25") if p != own_id and name(p)), "")
        kids.append({"name": label, "short": short, "other": other, "born": born["year"] if born else 9999})
    counted = [int(float(c["mainsnak"]["datavalue"]["value"]["amount"])) for c in statements(person, "P1971")]
    count = max([len(kids), *counted])
    if count:
        kids.sort(key=lambda k: k["born"])
        groups = {}
        for k in kids:
            groups.setdefault(k["other"], []).append(k["short"])
        if len(groups) > 1 and "" not in groups:
            parts = [f"{join(names)} with {other}" for other, names in groups.items()]
            listed = "; ".join(parts[:-1]) + "; and " + parts[-1]
        else:
            listed = join([k["short"] for k in kids]) if kids else ""
        more = count - len(kids)
        if more > 0:
            listed += f"{'; and ' if listed else ''}{more} more whose names aren't on public record"
        facts["Children"] = f"{count}: {listed}" if listed else str(count)
        noun = "child" if count == 1 else "children"
        answers["children"] = f"I {'have' if alive else 'had'} {count} {noun}" + (f": {listed}." if listed else ".")

    grandchildren = []
    for child in children.values():
        for gid in item_ids(child, "P40"):
            if name(gid) and name(gid) not in grandchildren:
                grandchildren.append(name(gid))
    if grandchildren:
        facts["Grandchildren"] = join(grandchildren)
        shown = grandchildren if len(grandchildren) <= 8 else grandchildren[:8]
        answers["grandchildren"] = (f"I {'have' if alive else 'had'} {len(grandchildren)} grandchild"
                                    f"{'ren' if len(grandchildren) > 1 else ''} on public record"
                                    f"{', including' if len(shown) < len(grandchildren) else ':'} {join(shown)}.")

    relatives = kin_named("P1038")
    if relatives:
        facts["Other relatives"] = join(relatives)

    # "How many relatives...?": the whole family on public record in one answer
    parents = [name(q) for pid in ("P22", "P25") for q in item_ids(person, pid)[:1] if name(q)]
    summary = []
    if parents:
        summary.append(f"my parents {join(parents)}")
    if siblings:
        summary.append(f"{len(siblings)} sibling{'s' if len(siblings) > 1 else ''}")
    if marriages:
        summary.append(f"{len(marriages)} marriage{'s' if len(marriages) > 1 else ''}")
    if count:
        summary.append(f"{count} {'child' if count == 1 else 'children'}")
    if grandchildren:
        summary.append(f"{len(grandchildren)} grandchild{'ren' if len(grandchildren) > 1 else ''}")
    if relatives:
        summary.append(f"other relatives such as {join(relatives[:4])}")
    if len(summary) > 1:
        answers["family"] = f"My family on public record: {join(summary)}."
    return facts, answers


def _net_worth(person: dict, labels: dict) -> tuple[dict, dict]:
    """Latest and highest net worth estimates (USD) with their dates and sources."""
    found = []
    for c in person.get("claims", {}).get("P2218", []):
        v = c["mainsnak"].get("datavalue", {}).get("value", {})
        when = qualifier_time(c, "P585")
        if c["rank"] == "deprecated" or v.get("unit") != USD or not when:
            continue
        stated = [s["datavalue"]["value"]["id"] for ref in c.get("references", [])
                  for s in ref.get("snaks", {}).get("P248", []) if s.get("snaktype") == "value"]
        source = next((labels[s]["label"] for s in stated if s in labels), "")
        found.append({"amount": float(v["amount"]), "when": when, "source": source})
    if not found:
        return {}, {}
    latest = max(found, key=lambda f: f["when"])
    peak = max(found, key=lambda f: f["amount"])
    by = f"{latest['source']} estimated" if latest["source"] else "The latest public estimate put"
    facts = {"Net worth": f"about {money(latest['amount'])} ({latest['source'] or 'estimate'}, {time_text(latest['when'])})",
             "Highest net worth on record": f"about {money(peak['amount'])} ({time_text(peak['when'])})"}
    answers = {
        "net_worth": f"{by} my net worth at about {money(latest['amount'])} as of {time_text(latest['when'])}. "
                     "Estimates like this move every day with share prices.",
        "peak_net_worth": f"The highest estimate of my net worth on public record is about {money(peak['amount'])}, "
                          f"from {time_text(peak['when'])}." + (" That's also the latest one." if peak is latest else ""),
    }
    return facts, answers


def build_profile(figure: dict, person: dict, labels: dict, children: dict | None = None) -> dict:
    children = children or {}

    def names(pid, limit=None, sort_by=None):
        claims = statements(person, pid)
        if sort_by:
            claims = sorted(claims, key=lambda c: qualifier_time(c, sort_by) or "+9999")
        out = []
        for c in claims:
            label = (labels.get(c["mainsnak"]["datavalue"]["value"]["id"], {}).get("label") or "").rstrip(".")
            if label and label.lower() not in (o.lower() for o in out):
                out.append(label)
        return out[:limit] if limit else out

    def place(pid):
        ids = item_ids(person, pid)
        if not ids or ids[0] not in labels:
            return ""
        p = labels[ids[0]]
        return f"{p['label']}, {p['country']}" if p.get("country") and p["country"] != p["label"] else p["label"]

    born, died = best_date(person, "P569"), best_date(person, "P570")
    alive = died is None
    is_ = "am" if alive else "was"
    born_in, died_in = place("P19"), place("P20")
    birth_names = [c["mainsnak"]["datavalue"]["value"]["text"] for c in statements(person, "P1477")
                   if c["mainsnak"]["datavalue"]["value"].get("language") in ("en", "mul")]
    nobel_first = lambda c: "Nobel" not in labels.get(c["mainsnak"]["datavalue"]["value"]["id"], {}).get("label", "")
    awards = []
    for c in sorted(statements(person, "P166"), key=nobel_first):
        label = labels.get(c["mainsnak"]["datavalue"]["value"]["id"], {}).get("label")
        when = qualifier_time(c, "P585")
        if label and label not in [a.split(" (")[0] for a in awards]:
            awards.append(f"{label} ({int(when[1:5])})" if when else label)
    awards = awards[:5]

    facts, answers = {}, {}
    if birth_names:
        facts["Full name"] = birth_names[0]
        answers["full_name"] = f"My full name {'is' if alive else 'was'} {birth_names[0]}."
    if born:
        on = "on" if born["date"] else "in"
        facts["Born"] = ", ".join(x for x in (born["text"], born_in) if x)
        answers["born"] = f"I was born {on} {born['text']}."
        if born_in:
            answers["born_and_place"] = f"I was born {on} {born['text']} in {born_in}."
    if born_in:
        answers["birth_place"] = f"I was born in {born_in}."
    if died:
        on = "on" if died["date"] else "in"
        facts["Died"] = ", ".join(x for x in (died["text"], died_in) if x)
        answers["died"] = f"I died {on} {died['text']}" + (f" in {died_in}." if died_in else ".")
        if born and born["date"] and died["date"]:
            b, d = born["date"], died["date"]
            age = d.year - b.year - ((d.month, d.day) < (b.month, b.day))
            answers["age"] = f"I died in {d.year}, at the age of {age}."
        elif born:
            answers["age"] = f"I lived from {born['year']} to {died['year']}."
    for key, pid, label in (("father", "P22", "Father"), ("mother", "P25", "Mother")):
        if names(pid):
            facts[label] = names(pid)[0]
            answers[key] = f"My {key} {'is' if alive else 'was'} {names(pid)[0]}."
    family_facts, family_answers = _family(person, labels, children, figure["wikidata"], figure["name"].split()[-1], died)
    facts.update(family_facts)
    answers.update(family_answers)
    schools = names("P69", sort_by="P580")
    if schools:
        facts["Education"] = join(schools)
        answers["education"] = f"I studied at {join(schools)}."
    jobs = names("P106", limit=4)
    if jobs:
        facts["Occupation"] = join(jobs)
        answers["occupation"] = f"I {is_} {'an' if jobs[0][0].lower() in 'aeiou' else 'a'} {join(jobs)}."
    countries = names("P27")
    if countries:
        facts["Citizenship"] = join(countries)
        the = [f"the {c}" if c.startswith("United ") else c for c in countries]  # "the United States"
        answers["nationality"] = f"I {'am' if alive else 'was'} a citizen of {join(the)}."
    if awards:
        facts["Awards"] = join(awards)
        answers["awards"] = f"Awards I received: {join(awards)}."
    works = names("P800", limit=6)
    if works:
        facts["Known for"] = join(works)
        answers["notable_works"] = f"I'm best known for {join(works)}."
    worth_facts, worth_answers = _net_worth(person, labels)
    facts.update(worth_facts)
    answers.update(worth_answers)
    heights = [c["mainsnak"]["datavalue"]["value"] for c in statements(person, "P2048")
               if c["mainsnak"]["datavalue"]["value"].get("unit") in METRES]
    if heights:
        metres = float(heights[0]["amount"]) * METRES[heights[0]["unit"]]
        feet, inches = divmod(round(metres / 0.0254), 12)
        facts["Height"] = f"{metres:.2f} m ({feet} ft {inches} in)"
        answers["height"] = f"I {'am' if alive else 'was'} {metres:.2f} m tall, about {feet} ft {inches} in."
    for key, pid, label, sentence in (
            ("religion", "P140", "Religion", "My religion {v} {x}."),
            ("positions", "P39", "Positions held", "Positions I {h}: {x}."),
            ("party", "P102", "Political party", "I {a} a member of the {x}."),
            ("languages", "P1412", "Languages", "I {s} {x}."),
            ("cause_of_death", "P509", "Cause of death", "The recorded cause of my death was {x}."),
            ("burial", "P119", "Resting place", "I was laid to rest at {x}.")):
        values = names(pid, limit=5)
        if values and not (alive and key in ("cause_of_death", "burial")):
            facts[label] = join(values)
            answers[key] = sentence.format(v="is" if alive else "was", a="am" if alive else "was", h="have held" if alive else "held",
                                           s="speak" if alive else "spoke", x=join(values))
    aliases = [a["value"] for lang in ("en", "mul") for a in person.get("aliases", {}).get(lang, [])]
    return {
        "person": figure["name"], "source": "Wikidata", "wikidata": figure["wikidata"],
        "url": f"https://www.wikidata.org/wiki/{figure['wikidata']}", "license": "CC0 1.0 (public domain)",
        "retrieved": date.today().isoformat(),
        "note": "Public-record facts about the person, not their own words. Edit to correct.",
        "living": alive, "birth_date": born["date"].isoformat() if alive and born and born["date"] else None,
        "aliases": sorted({a for a in aliases if 2 < len(a) <= 40 and not any(ch.isdigit() for ch in a)}),
        "facts": facts, "answers": answers,
    }


def apply_overrides(profile: dict, overrides: dict) -> dict:
    """Hand-checked corrections (figures/profile_overrides.json); None removes an entry."""
    for part in ("facts", "answers"):
        for key, value in overrides.get(part, {}).items():
            if value is None:
                profile[part].pop(key, None)
            else:
                profile[part][key] = value
    if overrides.get("aliases"):
        profile["aliases"] = sorted(set(profile["aliases"]) | set(overrides["aliases"]))
    if overrides:
        profile["note"] += " Some entries were corrected or added by hand (figures/profile_overrides.json)."
    return profile


def fetch(figure: dict) -> dict:
    person = get_entities([figure["wikidata"]], "labels|aliases|claims")[figure["wikidata"]]
    label = label_of(person) or ""
    if label != figure["name"]:
        raise ValueError(f"{figure['wikidata']} is '{label}', not {figure['name']}")
    # Children's own entries give whom each child was with, and the grandchildren
    child_ids = item_ids(person, "P40")
    children = get_entities(child_ids, "claims") if child_ids else {}
    linked = {i for pid in LINKED for i in item_ids(person, pid)}
    linked |= {q for pid in ("P3373", "P1038") for c in statements(person, pid) for q in qualifier_ids(c, "P1039")}
    linked |= {s["datavalue"]["value"]["id"] for c in person.get("claims", {}).get("P2218", [])
               for ref in c.get("references", []) for s in ref.get("snaks", {}).get("P248", []) if s.get("snaktype") == "value"}
    linked |= {i for child in children.values() for pid in ("P22", "P25", "P40") for i in item_ids(child, pid)}
    entities = get_entities(sorted(linked), "labels")
    # Birth/death places get their country: "Porbandar, India"
    places = sorted({p for pid in ("P19", "P20") for p in item_ids(person, pid)})
    place_claims = get_entities(places, "claims") if places else {}
    country_of = {p: (item_ids(place_claims.get(p, {}), "P17") or [None])[0] for p in places}
    missing = sorted({c for c in country_of.values() if c and c not in entities})
    if missing:
        entities.update(get_entities(missing, "labels"))
    labels = {qid: {"label": label_of(e),
                    "country": label_of(entities.get(country_of[qid], {})) if country_of.get(qid) else None}
              for qid, e in entities.items() if label_of(e)}
    return build_profile(figure, person, labels, children)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch public-record profile facts from Wikidata")
    parser.add_argument("--only", help="one figure id")
    args = parser.parse_args()
    figures = json.loads((ROOT / "figures" / "sources.json").read_text(encoding="utf-8"))["figures"] + ALSO
    overrides = json.loads((ROOT / "figures" / "profile_overrides.json").read_text(encoding="utf-8"))
    for figure in figures:
        if not figure.get("wikidata") or (args.only and figure["id"] != args.only):
            continue
        profile = apply_overrides(fetch(figure), overrides.get(figure["id"], {}))
        out = ROOT / "models" / figure["id"] / "profile.json"
        out.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{figure['id']}: {len(profile['answers'])} answers -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
