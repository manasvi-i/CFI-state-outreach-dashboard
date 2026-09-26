import json, re, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'source' / 'all-states-consolidated.json'
OUT = ROOT / 'data.json'

with open(SRC) as f:
    raw = json.load(f)

PROBLEM_AREAS = [
    {"id": "policy", "label": "Policy & Regulation"},
    {"id": "enforcement", "label": "Enforcement"},
    {"id": "engineering", "label": "Road Engineering"},
    {"id": "emergency_response", "label": "Emergency Response"},
    {"id": "data_monitoring", "label": "Data & Monitoring"},
    {"id": "education", "label": "Education & Awareness"},
    {"id": "funding", "label": "Funding"},
]

KEYWORDS = {
    "policy": [r"\bpolicy\b", r"\bact\b", r"\brules?\b", r"\bauthority\b", r"\bcommission\b",
               r"\bcabinet\b", r"\bregulat", r"\blicen[cs]", r"\bmotor vehicles? act\b",
               r"\bnodal\b", r"\bstatute\b", r"\bgovernment order\b", r"\bpermits?\b"],
    "enforcement": [r"\bpolice\b", r"\btraffic police\b", r"\benforcement\b", r"\bdgp\b", r"\bcommissioner of police\b",
                     r"\bsuperintendent of police\b", r"\bs\.?p\.?\b", r"\bssp\b", r"\blaw and order\b",
                     r"\bchallan", r"\bhome guards?\b", r"\bpatrol", r"\bconstabul"],
    "engineering": [r"\bhighways?\b", r"\bpublic works\b", r"\bpwd\b", r"\br\s?&\s?b\b",
                     r"\bconstruct", r"\binfrastructure\b", r"\bbridges?\b", r"\bflyovers?\b",
                     r"\bnhai\b", r"\brural development\b", r"\bblack ?spots?\b",
                     r"\bcorridors?\b", r"\bstate highways?\b",
                     r"\bexpressways?\b", r"\bcarriageway\b", r"\bfootpaths?\b", r"\bstreetlights?\b",
                     r"\broads? and buildings\b(?!\s+safety)", r"\bchief engineer\b",
                     r"\bexecutive engineer\b", r"\bengineer-in-chief\b", r"\bsuperintending engineer\b",
                     r"\broads?\b(?!\s+safety)"],
    "emergency_response": [r"\bhealth\b", r"\bambulance", r"\btrauma\b", r"\bhospital", r"\bmedical\b",
                            r"\bdisaster management\b", r"\bemergency\b", r"\b108\b", r"\bfire (and|&) rescue\b",
                            r"\bgolden hour\b", r"\bems\b"],
    "data_monitoring": [r"\bdata\b", r"\bdashboard", r"\birad\b", r"\bresearch\b", r"\biit\b",
                         r"\bcentre of excellence\b", r"\bmonitoring\b", r"\bsurvey", r"\baudit",
                         r"\banalytics\b", r"\bstatistics\b", r"\bmis\b"],
    "education": [r"\beducation\b", r"\bschools?\b", r"\btraining\b", r"\bawareness\b", r"\bcampaign",
                  r"\bconclave\b", r"\bdriving school", r"\bsensiti[sz]ation\b", r"\bworkshops?\b"],
    "funding": [r"\bfund\b", r"\bfunds\b", r"\bcess\b", r"\bbudget\b", r"\bfinance\b", r"\bworld bank\b",
                r"\bpmgsy\b", r"\bgrants?\b", r"\bscheme\b", r"\ballocation\b", r"\bcorpus\b"],
}
COMPILED = {k: [re.compile(p, re.I) for p in v] for k, v in KEYWORDS.items()}


def matches(text, cat):
    return any(p.search(text) for p in COMPILED[cat])


def classify_body(gb):
    name = str(gb.get("name", ""))
    mandate = str(gb.get("mandate", ""))
    roads_owned = str(gb.get("roads_owned", ""))
    data_role = str(gb.get("data_role", ""))
    decision = str(gb.get("decision_making_power", ""))
    subordinate = str(gb.get("subordinate_bodies", ""))

    primary = name + " " + mandate  # curated, low-noise fields -> all categories
    ro_low = roads_owned.lower()
    roads_applicable = not any(neg in ro_low for neg in
                                ["not applicable", "n/a", "not a road-owning", "not a road owning",
                                 "no roads", "not road-owning"])

    tags = set()
    for cat in PROBLEM_AREAS:
        cid = cat["id"]
        if matches(primary, cid):
            tags.add(cid)
    if roads_applicable and matches(roads_owned, "engineering"):
        tags.add("engineering")
    if matches(data_role, "data_monitoring"):
        tags.add("data_monitoring")
    if matches(data_role, "funding"):
        tags.add("funding")
    if matches(decision, "policy"):
        tags.add("policy")
    if matches(subordinate, "engineering") or matches(subordinate, "data_monitoring") or matches(subordinate, "emergency_response") or matches(subordinate, "education"):
        for cid in ("engineering", "data_monitoring", "emergency_response", "education"):
            if matches(subordinate, cid):
                tags.add(cid)
    if not tags:
        tags = {"policy"}
    return sorted(tags)


# Manual overrides for bodies where keyword heuristics misfire (e.g. an academic
# institute whose name contains "Engineering Design" but is not an engineering body).
TAG_OVERRIDES = {
    "tn-iit-madras-coe-road-safety": ["data_monitoring", "education"],
}


def confidence_badge(text):
    if not text:
        return "UNSPECIFIED"
    t = text.lower()
    if "unverified" in t:
        return "UNVERIFIED"
    if "stale" in t:
        return "LIKELY STALE"
    if "partially verified" in t:
        return "PARTIALLY VERIFIED"
    if "single-source" in t or "not independently" in t:
        return "UNVERIFIED"
    if "corrected in this pass" in t:
        return "CORRECTED"
    if "resolved in this pass" in t:
        return "RESOLVED"
    if "verified" in t:
        return "VERIFIED"
    if "not established" in t:
        return "NOT ESTABLISHED"
    return "UNSPECIFIED"


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def name_tokens(s):
    # meaningful tokens (len>=3) from a name/title, for fuzzy flag matching
    return [t for t in norm(s).split() if len(t) >= 3]


def flags_matching(entity_text, candidates):
    """candidates: list of (key, searchable_name). Returns list of keys whose name overlaps entity_text."""
    et = norm(entity_text)
    hits = []
    for key, name in candidates:
        toks = name_tokens(name)
        if not toks:
            continue
        matches = sum(1 for t in toks if t in et)
        if matches >= 1 and (matches / len(toks) >= 0.4 or matches >= 2):
            hits.append(key)
    return hits


PROSE_MARKERS = [" was ", " is ", " asked ", " under ", " which ", " who ", " for ",
                  "not always", "provides", "constituted", "established", "piloted",
                  "elected", "administrative", " in the ", " to engage ", " by "]


def parse_subordinates(text):
    """Returns {"type": "list", "items": [...]} for a genuine name list, or
    {"type": "prose", "text": "..."} when the source field is a sentence/paragraph
    that would produce nonsense fragments if comma-split."""
    if not text or not isinstance(text, str):
        return {"type": "list", "items": []}
    t = text.strip()
    tl = t.lower()
    if tl.startswith(("none specified", "not established", "not applicable", "none specifically",
                       "no formal", "not formally")) or t in ("—", "N/A"):
        return {"type": "list", "items": []}

    def split_on(sep, s):
        parts, depth, cur = [], 0, ""
        for ch in s:
            if ch == "(":
                depth += 1
            if ch == ")":
                depth = max(0, depth - 1)
            if ch == sep and depth == 0:
                parts.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur.strip())
        return parts

    if ";" in t:
        raw_items = split_on(";", t)
    else:
        word_count = len(t.split())
        looks_prose = word_count > 22 or any(m in f" {tl} " for m in PROSE_MARKERS)
        if t.count(",") >= 1 and not looks_prose:
            raw_items = split_on(",", t)
        else:
            return {"type": "prose", "text": t}

    items = []
    for p in raw_items:
        p = p.strip(" .")
        if not p or p.lower().startswith(("and others", "and other", "etc")):
            continue
        items.append(p)
    if not items:
        return {"type": "prose", "text": t}
    return {"type": "list", "items": items[:12]}


# Only distinctive, low-ambiguity title tokens are auto-matched to body-level prose.
# Generic ranks (SP/DSP/DCP/CP/Collector/Secretary/Minister) are deliberately excluded
# because a body can hold several such posts and a loose match would misattribute a
# generic sentence to the wrong specific person — see instructions: never invent
# specificity the source doesn't actually contain.
TITLE_ALIASES = {
    "dgp": ["dgp", "director general of police"],
    "engineer-in-chief": ["engineer-in-chief", "engineer in chief"],
    "chief engineer": ["chief engineer"],
    "transport commissioner": ["transport commissioner", "commissioner of transport",
                               "director of transport and road safety"],
    "chief secretary": ["chief secretary"],
    "additional chief secretary": ["additional chief secretary"],
}


def sentence_split(text):
    if not text:
        return []
    # naive sentence splitter good enough for these prose fields
    parts = re.split(r'(?<=[.;])\s+(?=[A-Z(])', text)
    return [p.strip() for p in parts if p.strip()]


def find_context_note(title, body_texts):
    title_low = title.lower()
    tokens = set()
    for key, aliases in TITLE_ALIASES.items():
        if key in title_low:
            tokens.update(aliases)
    if not tokens:
        return None
    for text in body_texts:
        for sent in sentence_split(text):
            sl = sent.lower()
            if any(tok in sl for tok in tokens):
                return sent
    return None


def parse_hierarchy_chain(text):
    if not text or not isinstance(text, str):
        return []
    if "→" in text:
        chain = [c.strip() for c in text.split("→") if c.strip()]
        return chain[:10]
    return []


out = {"meta": raw.get("meta", {}), "problem_areas": PROBLEM_AREAS, "flag_totals": raw.get("flag_totals", {}),
       "notable_corrections": raw.get("notable_corrections", []), "states": {}}

for sid, st in raw["states"].items():
    gbs = st.get("governance_bodies", [])
    flags = st.get("flags", [])
    people = st.get("key_individuals", [])

    # candidates for flag-matching: bodies (by name + key position names), people (by name)
    body_candidates = []
    for gb in gbs:
        body_candidates.append((gb["id"], gb["name"]))
    people_candidates = [(str(i), p.get("name", "")) for i, p in enumerate(people)]

    flags_out = []
    for fl in flags:
        entity = fl.get("entity", "") or fl.get("fact", "")
        body_hits = flags_matching(entity, body_candidates)
        people_hits = flags_matching(entity, people_candidates)
        flags_out.append({
            **fl,
            "linked_body_ids": body_hits,
            "linked_people_idx": [int(i) for i in people_hits],
        })

    gbs_out = []
    for gb in gbs:
        tags = TAG_OVERRIDES.get(gb["id"], classify_body(gb))
        kp_out = []
        body_texts = [gb.get("decision_making_power", ""), gb.get("mandate", ""),
                      gb.get("performance_issues", ""), gb.get("data_role", "")]
        for kp in gb.get("key_positions", []):
            note = find_context_note(kp.get("title", ""), body_texts)
            kp_out.append({
                **kp,
                "confidence_badge": confidence_badge(kp.get("confidence", "")),
                "context_note": note,
            })
        # find flags whose linked_body_ids include this body
        own_flags = [i for i, fl in enumerate(flags_out) if gb["id"] in fl["linked_body_ids"]]
        # The source data ties a citation to each *key position*, not to each prose field
        # (mandate/hierarchy/decision_making_power/etc.) — there is no sentence-level
        # citation for those. Rather than show "no citation on file" for every governance
        # body's mandate and reporting-line text, derive an honest body-level source list
        # from the same citations already verified for that body's key positions (the
        # department pages, notifications, and press coverage the research actually used).
        # index.html labels this explicitly as "sources used to verify this body's key
        # positions," not a claim that a specific sentence traces to a specific link.
        seen_urls = set()
        derived_citations = []
        for kp in gb.get("key_positions", []):
            c = kp.get("citation")
            if c and (c.get("url") or c.get("label")):
                key = c.get("url") or c.get("label")
                if key not in seen_urls:
                    seen_urls.add(key)
                    derived_citations.append(c)
        gbs_out.append({
            **gb,
            "key_positions": kp_out,
            "problem_areas": tags,
            "subordinates_parsed": parse_subordinates(gb.get("subordinate_bodies", "")),
            "hierarchy_chain": parse_hierarchy_chain(gb.get("hierarchy", "")),
            "flag_indices": own_flags,
            "has_post_level_detail": len(kp_out) > 0,
            "derived_citations": derived_citations,
        })

    people_out = []
    for idx, p in enumerate(people):
        own_flags = [i for i, fl in enumerate(flags_out) if idx in fl["linked_people_idx"]]
        people_out.append({**p, "flag_indices": own_flags, "_idx": idx})

    out["states"][sid] = {
        "state_id": sid,
        "state_name": st.get("state_name", sid),
        "political_context": st.get("political_context"),
        "cabinet_map": st.get("cabinet_map", []),
        "governance_bodies": gbs_out,
        "road_ownership_matrix": st.get("road_ownership_matrix", []),
        "district_level_actors": st.get("district_level_actors", []),
        "quick_reference_matrix": st.get("quick_reference_matrix", []),
        "funding_architecture": st.get("funding_architecture", []),
        "focus_areas": st.get("focus_areas", []),
        "key_individuals": people_out,
        "research_gaps": st.get("research_gaps", []),
        "flags": flags_out,
        "flag_count": len(flags_out),
    }

with open(OUT, "w") as f:
    json.dump(out, f, ensure_ascii=False)

print("done. size bytes:", len(json.dumps(out)))
# quick sanity print of tag distribution
from collections import Counter
c = Counter()
for sid, st in out["states"].items():
    for gb in st["governance_bodies"]:
        for t in gb["problem_areas"]:
            c[t] += 1
print(c)
