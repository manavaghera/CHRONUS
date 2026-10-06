"""
Basic public-record facts for the famous-figure models, from Wikidata (CC0).

For each figure in figures/sources.json ("wikidata" id) this writes
models/<id>/profile.json with
  - "facts":   short label -> value lines for the AI voice's prompt
  - "answers": first-person sentences for quick profile questions
               ("Which year were you born, and where?"), see services/profile.py
These are public records about the person, not their own words, and the
chat labels them that way. Re-run to refresh; edit the JSON to correct.

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
HEADERS = {"User-Agent": "CHRONUS-research/0.1 (university research project; profile facts for public-domain figures)"}
GREGORIAN = "http://www.wikidata.org/entity/Q1985727"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


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


def join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def build_profile(figure: dict, person: dict, labels: dict) -> dict:
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
        answers["full_name"] = f"My full name was {birth_names[0]}."
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
            answers[key] = f"My {key} was {names(pid)[0]}."
    if names("P3373"):
        siblings = names("P3373")
        facts["Siblings"] = join(siblings)
        answers["siblings"] = (f"I had one sibling, {siblings[0]}." if len(siblings) == 1 else
                               f"My siblings were {join(siblings)}.")
    spouses = names("P26", sort_by="P580")
    if spouses:
        facts["Spouse"] = join(spouses)
        answers["spouse"] = (f"I was married to {spouses[0]}." if len(spouses) == 1 else
                             f"I was married {'twice' if len(spouses) == 2 else f'{len(spouses)} times'}: first to {spouses[0]}, then to {join(spouses[1:])}.")
    children = names("P40")
    if children:
        facts["Children"] = join(children)
        answers["children"] = (f"I had one child, {children[0]}." if len(children) == 1 else
                               f"I had {len(children)} children: {join(children)}.")
    schools = names("P69", sort_by="P580")
    if schools:
        facts["Education"] = join(schools)
        answers["education"] = f"I studied at {join(schools)}."
    jobs = names("P106", limit=4)
    if jobs:
        facts["Occupation"] = join(jobs)
        answers["occupation"] = f"I was {'an' if jobs[0][0].lower() in 'aeiou' else 'a'} {join(jobs)}."
    countries = names("P27")
    if countries:
        facts["Citizenship"] = join(countries)
        answers["nationality"] = f"I was a citizen of {join(countries)}."
    if awards:
        facts["Awards"] = join(awards)
        answers["awards"] = f"Awards I received: {join(awards)}."
    works = names("P800", limit=6)
    if works:
        facts["Known for"] = join(works)
        answers["notable_works"] = f"I'm best known for {join(works)}."

    return {
        "person": figure["name"], "source": "Wikidata", "wikidata": figure["wikidata"],
        "url": f"https://www.wikidata.org/wiki/{figure['wikidata']}", "license": "CC0 1.0 (public domain)",
        "retrieved": date.today().isoformat(),
        "note": "Public-record facts about the person, not their own words. Edit to correct.",
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
    if overrides:
        profile["note"] += " Some entries were corrected by hand (figures/profile_overrides.json)."
    return profile


def fetch(figure: dict) -> dict:
    person = get_entities([figure["wikidata"]], "labels|claims")[figure["wikidata"]]
    label = label_of(person) or ""
    if label != figure["name"]:
        raise ValueError(f"{figure['wikidata']} is '{label}', not {figure['name']}")
    linked = sorted({i for pid in ("P19", "P20", "P22", "P25", "P3373", "P26", "P40", "P69", "P106", "P27", "P166", "P800")
                     for i in item_ids(person, pid)})
    entities = get_entities(linked, "labels")
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
    return build_profile(figure, person, labels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch public-record profile facts from Wikidata")
    parser.add_argument("--only", help="one figure id")
    args = parser.parse_args()
    figures = json.loads((ROOT / "figures" / "sources.json").read_text(encoding="utf-8"))["figures"]
    overrides = json.loads((ROOT / "figures" / "profile_overrides.json").read_text(encoding="utf-8"))
    for figure in figures:
        if args.only and figure["id"] != args.only:
            continue
        profile = apply_overrides(fetch(figure), overrides.get(figure["id"], {}))
        out = ROOT / "models" / figure["id"] / "profile.json"
        out.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{figure['id']}: {len(profile['answers'])} answers -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
