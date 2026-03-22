#!/usr/bin/env python3
"""
Gematria Analysis — Hebrew letter values, sacred numbers, and timeline intersections.
Extracted from the Jubilee Engine source. Analyzes relationships between sacred numbers,
triangular numbers, digit sums, and event-year overlaps.

Usage:
  python3 scripts/gematria.py                      # full analysis
  python3 scripts/gematria.py --word YHWH          # lookup a specific word
  python3 scripts/gematria.py --value 2701          # analyze a specific value
  python3 scripts/gematria.py --number 37           # analyze a sacred number
  python3 scripts/gematria.py --factors              # show factor relationships only
  python3 scripts/gematria.py --timeline             # show timeline intersections only
"""

import os
import csv, sys, argparse, json, math
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))

# ── Hebrew Alphabet ─────────────────────────────────────────────────────────

HEBREW_ALPHABET = [
    # (letter, name, standard_value)
    ("א", "Aleph", 1),
    ("ב", "Bet", 2),
    ("ג", "Gimel", 3),
    ("ד", "Dalet", 4),
    ("ה", "He", 5),
    ("ו", "Vav", 6),
    ("ז", "Zayin", 7),
    ("ח", "Chet", 8),
    ("ט", "Tet", 9),
    ("י", "Yod", 10),
    ("כ", "Kaf", 20),
    ("ל", "Lamed", 30),
    ("מ", "Mem", 40),
    ("נ", "Nun", 50),
    ("ס", "Samekh", 60),
    ("ע", "Ayin", 70),
    ("פ", "Pe", 80),
    ("צ", "Tsade", 90),
    ("ק", "Qof", 100),
    ("ר", "Resh", 200),
    ("ש", "Shin", 300),
    ("ת", "Tav", 400),
]

HEBREW_FINAL_FORMS = [
    # (letter, name, standard_value, final_value)
    ("ך", "Final Kaf", 20, 500),
    ("ם", "Final Mem", 40, 600),
    ("ן", "Final Nun", 50, 700),
    ("ף", "Final Pe", 80, 800),
    ("ץ", "Final Tsade", 90, 900),
]

# ── Gematria Database (from Jubilee Engine source) ──────────────────────────

GDATA = [
    {"name": "YHWH", "heb": "יהוה", "value": 26, "note": "Pos 26/50 in every Jubilee = halfway"},
    {"name": "Elohim", "heb": "אלהים", "value": 86, "note": "Creator name"},
    {"name": "Yeshua", "heb": "ישוע", "value": 386, "note": ""},
    {"name": "Mashiach", "heb": "משיח", "value": 358, "note": ""},
    {"name": "Yovel (Jubilee)", "heb": "יובל", "value": 48, "note": "48x125=6000 entire system"},
    {"name": "Shemitah", "heb": "שמיטה", "value": 364, "note": "364/7=52 exactly (weeks in solar yr)"},
    {"name": "Moed (Appointed Time)", "heb": "מועד", "value": 120, "note": "= Total Jubilees in system"},
    {"name": "Ketz (The End)", "heb": "קץ", "value": 1000, "note": "= Millennium length"},
    {"name": "Chokhmah (Wisdom)", "heb": "חכמה", "value": 73, "note": "73x37=2701=Gen 1:1"},
    {"name": "Echad (One)", "heb": "אחד", "value": 13, "note": "= Ahavah (Love)"},
    {"name": "Ahavah (Love)", "heb": "אהבה", "value": 13, "note": "= Echad (One); YHWH=2xLove"},
    {"name": "Emet (Truth)", "heb": "אמת", "value": 441, "note": "441/7=63 exactly"},
    {"name": "Brit (Covenant)", "heb": "ברית", "value": 612, "note": ""},
    {"name": "Yisrael (Israel)", "heb": "ישראל", "value": 541, "note": "Prime number"},
    {"name": "Yerushalayim", "heb": "ירושלים", "value": 1156, "note": ""},
    {"name": "Shamayim (Heaven)", "heb": "שמים", "value": 950, "note": "950/50=19 exactly"},
    {"name": "Aleph-Tav", "heb": "את", "value": 401, "note": "Gen 1:1 obj marker; Aleph+Tav"},
    {"name": "Adam", "heb": "אדם", "value": 45, "note": ""},
    {"name": "Or (Light)", "heb": "אור", "value": 207, "note": "First created thing"},
    {"name": "Genesis 1:1 total", "heb": "בראשית...", "value": 2701, "note": "=37x73; 73rd triangular"},
    {"name": "Iesous (Greek)", "heb": "Ιησους", "value": 888, "note": "8x111; new beginning tripled"},
    {"name": "The number 777", "heb": "", "value": 777, "note": "Lamech lifespan; 7x111"},
    {"name": "The number 666", "heb": "", "value": 666, "note": "6x111; 6x3x37; .666 unfired position"},
]

# ── Sacred Numbers (from Jubilee Engine source) ─────────────────────────────

SACRED_NUMBERS = [
    {"value": 7, "significance": "Sabbath completion"},
    {"value": 12, "significance": "Tribes / Apostles"},
    {"value": 13, "significance": "Echad (One) = Ahavah (Love)"},
    {"value": 14, "significance": "2x7"},
    {"value": 21, "significance": "3x7 — .42 signature"},
    {"value": 26, "significance": "YHWH gematria; halfway in Jubilee"},
    {"value": 37, "significance": "Prime; 37x73=2701=Gen 1:1"},
    {"value": 40, "significance": "Trial/testing period"},
    {"value": 42, "significance": "Tribulation (42 months)"},
    {"value": 48, "significance": "Yovel gematria; 48x125=6000"},
    {"value": 49, "significance": "7x7 Shemitahs"},
    {"value": 50, "significance": "One Jubilee"},
    {"value": 70, "significance": "Seventy — full completion"},
    {"value": 73, "significance": "Chokhmah; 73x37=2701; prime"},
    {"value": 86, "significance": "Elohim gematria"},
    {"value": 100, "significance": "Full generation"},
    {"value": 111, "significance": "Aleph in full spelling (111); factor of 666,777,888"},
    {"value": 120, "significance": "Max lifespan / total Jubilees / Moed gematria"},
    {"value": 358, "significance": "Mashiach gematria"},
    {"value": 386, "significance": "Yeshua gematria"},
    {"value": 400, "significance": "Four generations (Gen 15:13)"},
    {"value": 401, "significance": "Aleph-Tav gematria"},
    {"value": 430, "significance": "Egypt sojourn"},
    {"value": 480, "significance": "Exodus to Temple (1 Kgs 6:1)"},
    {"value": 483, "significance": "69 weeks of Daniel"},
    {"value": 490, "significance": "70 weeks of Daniel"},
    {"value": 541, "significance": "Yisrael gematria; prime"},
    {"value": 666, "significance": "Number of the beast; 6x111; .666 unfired position"},
    {"value": 777, "significance": "Lamech lifespan; 7x111; divine perfection tripled"},
    {"value": 888, "significance": "Iesous (Greek); 8x111; new beginning tripled"},
    {"value": 1000, "significance": "Millennium; Ketz gematria"},
    {"value": 2701, "significance": "Genesis 1:1 total; 37x73; 73rd triangular number"},
]


# ── Utility Functions ───────────────────────────────────────────────────────

def digital_root(n):
    """Repeatedly sum digits until a single digit remains."""
    n = abs(n)
    while n >= 10:
        n = sum(int(d) for d in str(n))
    return n


def digit_sum(n):
    """Sum of all digits."""
    return sum(int(d) for d in str(abs(n)))


def is_triangular(n):
    """Check if n is a triangular number. Returns the index k if T(k)=n, else None."""
    if n < 0:
        return None
    # T(k) = k*(k+1)/2  =>  k = (-1 + sqrt(1+8n))/2
    discriminant = 1 + 8 * n
    sqrt_d = math.isqrt(discriminant)
    if sqrt_d * sqrt_d == discriminant and (sqrt_d - 1) % 2 == 0:
        k = (sqrt_d - 1) // 2
        if k * (k + 1) // 2 == n:
            return k
    return None


def triangular(k):
    """Return the k-th triangular number."""
    return k * (k + 1) // 2


def prime_factors(n):
    """Return list of prime factors."""
    if n <= 1:
        return []
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


def is_prime(n):
    """Simple primality test."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def to_am(year_ad, creation_bc=4004):
    """Convert AD year (negative=BC) to Anno Mundi."""
    return creation_bc + year_ad


# ── Data Loaders ────────────────────────────────────────────────────────────

def load_events():
    """Load events from data/events.csv."""
    events = []
    path = BASE / "data" / "events.csv"
    if not path.exists():
        return events
    with open(path) as f:
        for row in csv.DictReader(f):
            events.append({"name": row["name"], "year_ad": int(row["year_ad"])})
    return sorted(events, key=lambda e: e["year_ad"])


def load_database():
    """Load full database from output/database.csv if available."""
    rows = []
    path = BASE / "output" / "database.csv"
    if not path.exists():
        return rows
    with open(path) as f:
        for row in csv.DictReader(f):
            row["year_ad"] = int(row["year_ad"])
            row["am_year"] = int(row["am_year"])
            row["cosmic_jubilee"] = float(row["cosmic_jubilee"])
            row["cosmic_remainder"] = float(row["cosmic_remainder"])
            rows.append(row)
    return rows


def load_clocks():
    """Load clock definitions from data/clocks.json."""
    with open(BASE / "data" / "clocks.json") as f:
        return json.load(f)


# ── Analysis Functions ──────────────────────────────────────────────────────

def analyze_value(v):
    """Full analysis of a single numeric value."""
    result = {"value": v}

    # Divisibility by key numbers
    result["div_7"] = round(v / 7, 4)
    result["mod_7"] = v % 7
    result["div_50"] = round(v / 50, 4)
    result["mod_50"] = v % 50
    result["div_120"] = round(v / 120, 4)
    result["mod_120"] = v % 120

    # Digital root and digit sum
    result["digital_root"] = digital_root(v)
    result["digit_sum"] = digit_sum(v)

    # Triangular?
    tri_k = is_triangular(v)
    result["is_triangular"] = tri_k is not None
    result["triangular_index"] = tri_k if tri_k else ""

    # Prime?
    result["is_prime"] = is_prime(v)

    # Factors
    pf = prime_factors(v)
    result["prime_factors"] = "x".join(str(f) for f in pf) if pf else str(v)

    # As AM year => what date?
    if v <= 10000:
        year_ad = v - 4004
        result["as_am_date"] = f"{abs(year_ad)} BC" if year_ad < 0 else f"{year_ad} AD"
    else:
        result["as_am_date"] = ""

    # As Jubilee position
    j_pos = v / 50
    j_rem = round((j_pos % 1), 4)
    result["as_jubilee_pos"] = round(j_pos, 4)
    result["as_jubilee_rem"] = j_rem

    # Known word match
    matches = [g for g in GDATA if g["value"] == v]
    result["known_words"] = "; ".join(g["name"] for g in matches) if matches else ""

    # Sacred number match
    sacred = [s for s in SACRED_NUMBERS if s["value"] == v]
    result["sacred_significance"] = sacred[0]["significance"] if sacred else ""

    return result


def analyze_relationships():
    """Analyze relationships between all sacred numbers and gematria values."""
    all_values = set()
    for g in GDATA:
        all_values.add(g["value"])
    for s in SACRED_NUMBERS:
        all_values.add(s["value"])

    rows = []

    for v in sorted(all_values):
        analysis = analyze_value(v)

        # Find factor relationships with other sacred values
        factor_links = []
        for v2 in sorted(all_values):
            if v2 == v or v2 == 0:
                continue
            if v > v2 and v % v2 == 0:
                factor_links.append(f"{v}/{v2}={v // v2}")
            elif v2 > v and v2 % v == 0:
                factor_links.append(f"{v2}/{v}={v2 // v}")

        # Product relationships: does v = a * b where both are in our set?
        product_links = []
        for v2 in sorted(all_values):
            if v2 >= v or v2 == 0:
                continue
            if v % v2 == 0:
                quotient = v // v2
                if quotient in all_values and quotient != v2:
                    product_links.append(f"{v2}x{quotient}")

        # Sum relationships: does v = a + b?
        sum_links = []
        for v2 in sorted(all_values):
            if v2 >= v:
                break
            complement = v - v2
            if complement in all_values and complement > v2:
                sum_links.append(f"{v2}+{complement}")

        rows.append({
            "value": v,
            "known_word": analysis["known_words"],
            "sacred_significance": analysis["sacred_significance"],
            "prime_factors": analysis["prime_factors"],
            "is_prime": "PRIME" if analysis["is_prime"] else "",
            "is_triangular": f"T({analysis['triangular_index']})" if analysis["is_triangular"] else "",
            "digital_root": analysis["digital_root"],
            "digit_sum": analysis["digit_sum"],
            "div_7": f"{analysis['div_7']}" + (" *" if analysis["mod_7"] == 0 else ""),
            "div_50": f"{analysis['div_50']}" + (" *" if analysis["mod_50"] == 0 else ""),
            "factor_links": "; ".join(factor_links[:8]),
            "product_of": "; ".join(product_links[:5]),
            "sum_of": "; ".join(sum_links[:5]),
            "as_am_date": analysis["as_am_date"],
            "jubilee_pos": analysis["as_jubilee_pos"],
            "jubilee_rem": analysis["as_jubilee_rem"],
        })

    return rows


def find_timeline_intersections():
    """Find where sacred/gematria values appear in the event timeline."""
    events = load_events()
    database = load_database()

    all_values = {}
    for g in GDATA:
        all_values[g["value"]] = g["name"]
    for s in SACRED_NUMBERS:
        if s["value"] not in all_values:
            all_values[s["value"]] = s["significance"]

    rows = []

    for ev in events:
        yr = ev["year_ad"]
        am = to_am(yr)

        # Check if AM year matches any sacred value
        if am in all_values:
            rows.append({
                "event": ev["name"],
                "year_ad": yr,
                "am_year": am,
                "match_type": "AM year = sacred value",
                "matched_value": am,
                "meaning": all_values[am],
            })

        # Check if AM year is a multiple of sacred values
        for v, label in sorted(all_values.items()):
            if v <= 1 or am <= 0:
                continue
            if am % v == 0:
                mult = am // v
                if 2 <= mult <= 30:
                    rows.append({
                        "event": ev["name"],
                        "year_ad": yr,
                        "am_year": am,
                        "match_type": f"AM year = {mult}x sacred",
                        "matched_value": v,
                        "meaning": f"{mult}x {label} ({v})",
                    })

        # Check if the absolute year_ad matches sacred values
        abs_yr = abs(yr)
        if abs_yr in all_values and abs_yr > 0:
            rows.append({
                "event": ev["name"],
                "year_ad": yr,
                "am_year": am,
                "match_type": "Year magnitude = sacred value",
                "matched_value": abs_yr,
                "meaning": all_values[abs_yr],
            })

    # Check if gaps between events match gematria values
    for i, ev_a in enumerate(events):
        for j, ev_b in enumerate(events):
            if j <= i:
                continue
            gap = ev_b["year_ad"] - ev_a["year_ad"]
            if gap in all_values:
                rows.append({
                    "event": f"{ev_a['name']} -> {ev_b['name']}",
                    "year_ad": f"{ev_a['year_ad']} to {ev_b['year_ad']}",
                    "am_year": gap,
                    "match_type": "Gap = sacred value",
                    "matched_value": gap,
                    "meaning": f"{all_values[gap]} ({gap} years)",
                })

    return rows


def build_hebrew_alphabet_table():
    """Build analysis table for the Hebrew alphabet itself."""
    rows = []
    for letter, name, value in HEBREW_ALPHABET:
        analysis = analyze_value(value)
        rows.append({
            "letter": letter,
            "name": name,
            "standard_value": value,
            "form": "standard",
            "digital_root": digital_root(value),
            "is_prime": "PRIME" if is_prime(value) else "",
            "div_7": f"{value / 7:.4f}" + (" *" if value % 7 == 0 else ""),
        })
    for letter, name, std_val, final_val in HEBREW_FINAL_FORMS:
        rows.append({
            "letter": letter,
            "name": name,
            "standard_value": final_val,
            "form": "final",
            "digital_root": digital_root(final_val),
            "is_prime": "PRIME" if is_prime(final_val) else "",
            "div_7": f"{final_val / 7:.4f}" + (" *" if final_val % 7 == 0 else ""),
        })
    return rows


def build_111_family():
    """Analyze the 111 family: 111, 222, 333 ... 999 and key multiples."""
    rows = []
    for mult in range(1, 10):
        v = 111 * mult
        analysis = analyze_value(v)
        note = ""
        if v == 666:
            note = "Number of the beast; 6x3x37"
        elif v == 777:
            note = "Lamech lifespan; divine perfection tripled"
        elif v == 888:
            note = "Iesous (Greek gematria); new beginning tripled"
        elif v == 111:
            note = "Aleph in full spelling; unity"
        elif v == 333:
            note = "Half of 666"
        elif v == 444:
            note = "Damascus (Greek)"
        elif v == 555:
            note = "5x111"
        elif v == 222:
            note = "2x111"
        elif v == 999:
            note = "9x111; final digit tripled"

        rows.append({
            "value": v,
            "formula": f"{mult}x111",
            "also": f"{mult}x3x37",
            "digital_root": digital_root(v),
            "is_triangular": f"T({analysis['triangular_index']})" if analysis["is_triangular"] else "",
            "as_am_date": analysis["as_am_date"],
            "note": note,
        })
    return rows


def lookup_word(word_name):
    """Look up a specific word in the gematria database."""
    matches = [g for g in GDATA if word_name.lower() in g["name"].lower()]
    return matches


# ── Output Generator ────────────────────────────────────────────────────────

def generate_output(args):
    """Generate the full gematria analysis CSV and print summary."""

    all_rows = []
    sections = {}

    # ── Section 1: Sacred number relationships
    print("\n=== SACRED NUMBER & GEMATRIA RELATIONSHIPS ===")
    relationships = analyze_relationships()
    sections["relationships"] = relationships

    print(f"  Analyzed {len(relationships)} unique values")

    # Count notable properties
    primes = [r for r in relationships if r["is_prime"]]
    triangulars = [r for r in relationships if r["is_triangular"]]
    div7 = [r for r in relationships if "* " in str(r["div_7"]) or str(r["div_7"]).endswith("*")]
    div50 = [r for r in relationships if "* " in str(r["div_50"]) or str(r["div_50"]).endswith("*")]

    print(f"  Primes: {len(primes)} — {', '.join(str(r['value']) for r in primes)}")
    tri_strs = [f"{r['value']} ({r['is_triangular']})" for r in triangulars]
    print(f"  Triangular: {len(triangulars)} — {', '.join(tri_strs)}")
    print(f"  Divisible by 7: {len(div7)} values")
    print(f"  Divisible by 50: {len(div50)} values")

    # ── Section 2: Timeline intersections
    print("\n=== TIMELINE INTERSECTIONS ===")
    intersections = find_timeline_intersections()
    sections["intersections"] = intersections
    print(f"  Found {len(intersections)} intersections between sacred values and events")

    # Count by type
    by_type = defaultdict(int)
    for row in intersections:
        by_type[row["match_type"]] += 1
    for mtype, count in sorted(by_type.items()):
        print(f"    {mtype}: {count}")

    # ── Section 3: 111 family
    print("\n=== THE 111 FAMILY (NxNxN pattern) ===")
    family_111 = build_111_family()
    sections["family_111"] = family_111
    for row in family_111:
        note_str = f" — {row['note']}" if row["note"] else ""
        print(f"  {row['value']:>4} = {row['formula']:>5}  DR={row['digital_root']}  {row['is_triangular']}{note_str}")

    # ── Section 4: Hebrew alphabet
    print("\n=== HEBREW ALPHABET ===")
    alphabet = build_hebrew_alphabet_table()
    sections["alphabet"] = alphabet
    prime_letters = [r for r in alphabet if r["is_prime"] and r["form"] == "standard"]
    print(f"  22 letters + 5 final forms = 27 total")
    prime_strs = [f"{r['name']}({r['standard_value']})" for r in prime_letters]
    print(f"  Prime-valued letters: {', '.join(prime_strs)}")

    # ── Section 5: Key findings
    print("\n=== KEY FINDINGS ===")

    # Genesis 1:1 analysis
    print("  Genesis 1:1 value = 2701")
    print(f"    = 37 x 73 (both primes)")
    print(f"    = T(73) — the 73rd triangular number")
    print(f"    73 = Chokhmah (Wisdom) gematria")
    print(f"    37 = digital root 1; mirror of 73")
    print(f"    37 + 73 = 110 = Joseph's lifespan")

    # YHWH = 26 analysis
    print("  YHWH = 26")
    print(f"    Position 26 of 50 = exact midpoint of Jubilee")
    print(f"    26 = 2 x 13 = 2 x Ahavah (Love)")
    print(f"    Digital root: {digital_root(26)}")

    # 666/777/888 trinity
    print("  666 / 777 / 888 — the 111-triple system:")
    print(f"    666 = 6x111 = 6x3x37 = 18x37  DR={digital_root(666)}")
    print(f"    777 = 7x111 = 7x3x37 = 21x37  DR={digital_root(777)}")
    print(f"    888 = 8x111 = 8x3x37 = 24x37  DR={digital_root(888)}")
    print(f"    Shared prime factor: 37 (the Genesis 1:1 kernel)")
    print(f"    666+888 = 1554 = 2x777  — beast+Christ centers on perfection")

    # Moed = 120 = total Jubilees
    print("  Moed (Appointed Time) = 120 = total Jubilees in system")
    print(f"    120 = 3x40 (three testing periods)")
    print(f"    120 = 5x24 (grace x priesthood)")
    print(f"    120 years = Gen 6:3 lifespan limit")

    # ── Write combined CSV
    outfile = BASE / "output" / "gematria.csv"
    csv_rows = []

    # Relationships section
    for r in relationships:
        csv_rows.append({
            "section": "relationship",
            "value": r["value"],
            "name": r.get("known_word", ""),
            "significance": r.get("sacred_significance", ""),
            "prime_factors": r.get("prime_factors", ""),
            "is_prime": r.get("is_prime", ""),
            "is_triangular": r.get("is_triangular", ""),
            "digital_root": r.get("digital_root", ""),
            "digit_sum": r.get("digit_sum", ""),
            "div_7": r.get("div_7", ""),
            "div_50": r.get("div_50", ""),
            "factor_links": r.get("factor_links", ""),
            "product_of": r.get("product_of", ""),
            "sum_of": r.get("sum_of", ""),
            "as_am_date": r.get("as_am_date", ""),
            "jubilee_pos": r.get("jubilee_pos", ""),
            "jubilee_rem": r.get("jubilee_rem", ""),
            "match_type": "",
            "event": "",
            "year_ad": "",
            "am_year": "",
            "matched_value": "",
            "meaning": "",
        })

    # Timeline intersections section
    for r in intersections:
        csv_rows.append({
            "section": "timeline",
            "value": r.get("matched_value", ""),
            "name": "",
            "significance": "",
            "prime_factors": "",
            "is_prime": "",
            "is_triangular": "",
            "digital_root": "",
            "digit_sum": "",
            "div_7": "",
            "div_50": "",
            "factor_links": "",
            "product_of": "",
            "sum_of": "",
            "as_am_date": "",
            "jubilee_pos": "",
            "jubilee_rem": "",
            "match_type": r.get("match_type", ""),
            "event": r.get("event", ""),
            "year_ad": r.get("year_ad", ""),
            "am_year": r.get("am_year", ""),
            "matched_value": r.get("matched_value", ""),
            "meaning": r.get("meaning", ""),
        })

    # 111 family section
    for r in family_111:
        csv_rows.append({
            "section": "111_family",
            "value": r["value"],
            "name": r.get("note", ""),
            "significance": r.get("formula", ""),
            "prime_factors": r.get("also", ""),
            "is_prime": "",
            "is_triangular": r.get("is_triangular", ""),
            "digital_root": r.get("digital_root", ""),
            "digit_sum": "",
            "div_7": "",
            "div_50": "",
            "factor_links": "",
            "product_of": "",
            "sum_of": "",
            "as_am_date": r.get("as_am_date", ""),
            "jubilee_pos": "",
            "jubilee_rem": "",
            "match_type": "",
            "event": "",
            "year_ad": "",
            "am_year": "",
            "matched_value": "",
            "meaning": "",
        })

    # Alphabet section
    for r in alphabet:
        csv_rows.append({
            "section": "alphabet",
            "value": r["standard_value"],
            "name": f"{r['letter']} {r['name']}",
            "significance": r.get("form", ""),
            "prime_factors": "",
            "is_prime": r.get("is_prime", ""),
            "is_triangular": "",
            "digital_root": r.get("digital_root", ""),
            "digit_sum": "",
            "div_7": r.get("div_7", ""),
            "div_50": "",
            "factor_links": "",
            "product_of": "",
            "sum_of": "",
            "as_am_date": "",
            "jubilee_pos": "",
            "jubilee_rem": "",
            "match_type": "",
            "event": "",
            "year_ad": "",
            "am_year": "",
            "matched_value": "",
            "meaning": "",
        })

    if csv_rows:
        fieldnames = csv_rows[0].keys()
        with open(outfile, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

    total = len(csv_rows)
    print(f"\nOutput: {outfile}")
    print(f"Total rows: {total} ({len(relationships)} relationships, {len(intersections)} timeline, "
          f"{len(family_111)} 111-family, {len(alphabet)} alphabet)")

    return csv_rows


# ── Single-item modes ───────────────────────────────────────────────────────

def run_word_lookup(word_name):
    """Lookup and print analysis for a specific word."""
    matches = lookup_word(word_name)
    if not matches:
        print(f"No matches for '{word_name}' in gematria database.")
        print("Known words:")
        for g in GDATA:
            print(f"  {g['name']:30s} = {g['value']:>5}  {g['heb']}")
        return

    for g in matches:
        print(f"\n=== {g['name']} ===")
        print(f"  Hebrew: {g['heb']}")
        print(f"  Value:  {g['value']}")
        if g["note"]:
            print(f"  Note:   {g['note']}")

        a = analyze_value(g["value"])
        print(f"  Digital root:    {a['digital_root']}")
        print(f"  Digit sum:       {a['digit_sum']}")
        print(f"  Prime factors:   {a['prime_factors']}")
        print(f"  Is prime:        {a['is_prime']}")
        tri_label = f"T({a['triangular_index']})" if a['is_triangular'] else ""
        print(f"  Is triangular:   {a['is_triangular']} {tri_label}")
        print(f"  div 7:           {a['div_7']} {'EXACT' if a['mod_7'] == 0 else ''}")
        print(f"  div 50:          {a['div_50']} {'EXACT' if a['mod_50'] == 0 else ''}")
        print(f"  As AM year:      {a['as_am_date']}")
        print(f"  As Jubilee pos:  J {a['as_jubilee_pos']} (rem {a['as_jubilee_rem']})")


def run_value_analysis(v):
    """Analyze a specific numeric value."""
    print(f"\n=== VALUE ANALYSIS: {v} ===")
    a = analyze_value(v)

    # Known matches
    if a["known_words"]:
        print(f"  Known as:        {a['known_words']}")
    if a["sacred_significance"]:
        print(f"  Sacred:          {a['sacred_significance']}")

    print(f"  Prime factors:   {a['prime_factors']}")
    print(f"  Is prime:        {a['is_prime']}")
    tri_str = f"T({a['triangular_index']})" if a["is_triangular"] else "No"
    print(f"  Is triangular:   {tri_str}")
    print(f"  Digital root:    {a['digital_root']}")
    print(f"  Digit sum:       {a['digit_sum']}")
    print(f"  div 7:           {a['div_7']} {'EXACT' if a['mod_7'] == 0 else ''}")
    print(f"  div 50:          {a['div_50']} {'EXACT' if a['mod_50'] == 0 else ''}")
    print(f"  div 120:         {a['div_120']} {'EXACT' if a['mod_120'] == 0 else ''}")
    if a["as_am_date"]:
        print(f"  As AM year:      {a['as_am_date']}")
    print(f"  Jubilee pos:     J {a['as_jubilee_pos']} (rem {a['as_jubilee_rem']})")

    # Multiples that hit events
    events = load_events()
    if events:
        print(f"\n  Multiples hitting events (AM years):")
        hits = 0
        for mult in range(1, 200):
            product = v * mult
            for ev in events:
                am = to_am(ev["year_ad"])
                if am == product:
                    print(f"    {v} x {mult} = AM {product} = {ev['name']} ({ev['year_ad']})")
                    hits += 1
                elif 0 < abs(am - product) <= 2:
                    print(f"    {v} x {mult} = AM {product} ~ AM {am} = {ev['name']} (off by {am - product})")
                    hits += 1
            if product > 10000:
                break
        if hits == 0:
            print("    (none found)")


def run_number_analysis(n):
    """Deep-dive into a specific sacred number."""
    print(f"\n=== SACRED NUMBER DEEP-DIVE: {n} ===")

    # Basic properties
    a = analyze_value(n)
    if a["sacred_significance"]:
        print(f"  Significance:  {a['sacred_significance']}")
    if a["known_words"]:
        print(f"  Gematria match: {a['known_words']}")
    print(f"  Prime factors: {a['prime_factors']}")
    print(f"  Digital root:  {a['digital_root']}")

    # Where does this number appear in the 111 family?
    if n > 0 and 111 % n == 0:
        print(f"  111 / {n} = {111 // n}")
    if n > 0 and n % 37 == 0:
        print(f"  {n} / 37 = {n // 37}  (Genesis 1:1 kernel)")

    # Products with other sacred numbers
    print(f"\n  Products with other sacred values:")
    for s in SACRED_NUMBERS:
        sv = s["value"]
        if sv == n:
            continue
        product = n * sv
        # Check if product is meaningful
        known = [g for g in GDATA if g["value"] == product]
        sacred_match = [s2 for s2 in SACRED_NUMBERS if s2["value"] == product]
        if known or sacred_match or product == 2701 or product == 6000 or product % 1000 == 0:
            label = ""
            if known:
                label = known[0]["name"]
            elif sacred_match:
                label = sacred_match[0]["significance"]
            elif product == 2701:
                label = "Genesis 1:1"
            elif product == 6000:
                label = "Work period (6000 of 8000-year plan)"
            elif product % 1000 == 0:
                label = f"{product // 1000} millennia"
            print(f"    {n} x {sv} = {product}  {label}")

    # Gaps in the timeline
    events = load_events()
    print(f"\n  Events separated by exactly {n} years:")
    found = 0
    for i, a_ev in enumerate(events):
        for j, b_ev in enumerate(events):
            if j <= i:
                continue
            gap = b_ev["year_ad"] - a_ev["year_ad"]
            if gap == n:
                print(f"    {a_ev['name']} ({a_ev['year_ad']}) -> {b_ev['name']} ({b_ev['year_ad']})")
                found += 1
    if found == 0:
        # Check multiples
        print(f"    (no exact matches; checking multiples...)")
        for mult in range(2, 11):
            target = n * mult
            for i, a_ev in enumerate(events):
                for j, b_ev in enumerate(events):
                    if j <= i:
                        continue
                    gap = b_ev["year_ad"] - a_ev["year_ad"]
                    if gap == target:
                        print(f"    {mult}x{n}={target}: {a_ev['name']} ({a_ev['year_ad']}) -> {b_ev['name']} ({b_ev['year_ad']})")
                        found += 1
                        if found >= 10:
                            break
                if found >= 10:
                    break
            if found >= 10:
                break


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Hebrew gematria analysis — sacred numbers, relationships, and timeline intersections"
    )
    parser.add_argument("--word", "-w", type=str, help="Look up a specific word (e.g., YHWH, Yeshua)")
    parser.add_argument("--value", "-v", type=int, help="Analyze a specific numeric value")
    parser.add_argument("--number", "-n", type=int, help="Deep-dive into a sacred number")
    parser.add_argument("--factors", "-f", action="store_true", help="Show factor relationships only")
    parser.add_argument("--timeline", "-t", action="store_true", help="Show timeline intersections only")
    args = parser.parse_args()

    if args.word:
        run_word_lookup(args.word)
        return

    if args.value:
        run_value_analysis(args.value)
        return

    if args.number:
        run_number_analysis(args.number)
        return

    if args.factors:
        relationships = analyze_relationships()
        print(f"Factor relationships for {len(relationships)} values:\n")
        for r in relationships:
            if r["factor_links"] or r["product_of"]:
                print(f"  {r['value']:>5}  {r.get('known_word', ''):30s}  factors: {r['factor_links']}")
                if r["product_of"]:
                    print(f"         {'':30s}  product: {r['product_of']}")
        return

    if args.timeline:
        intersections = find_timeline_intersections()
        print(f"Timeline intersections: {len(intersections)}\n")
        for r in intersections:
            print(f"  {r['event']:45s}  {str(r['year_ad']):>12}  {r['match_type']:30s}  {r['meaning']}")
        return

    # Full analysis
    print("Jubilee Lab — Gematria Analysis Engine")
    print("=" * 50)
    generate_output(args)


if __name__ == "__main__":
    main()
