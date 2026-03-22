#!/usr/bin/env python3
"""
Jubilee Lab — Auto-Tag Enrichment
Automatically assigns tags to events based on rules derived from the data.
Run this to auto-populate tags, then manually refine.
"""

import os
import csv, json, re, argparse
from pathlib import Path
from collections import defaultdict

BASE = Path(os.environ.get("LAB_INSTANCE", Path.cwd()))
DATA = BASE / "data"
OUT = BASE / "output"

def load_events():
    with open(DATA / "events.csv", newline="") as f:
        return list(csv.DictReader(f))

def load_signatures():
    with open(DATA / "signatures.json") as f:
        return json.load(f)

def load_database():
    with open(OUT / "database.csv", newline="") as f:
        return list(csv.DictReader(f))

def to_am(year_ad):
    return 4004 + int(year_ad)

def auto_tag(ev, db_row):
    """Generate tags for an event based on rules"""
    tags = set()
    yr = int(ev["year_ad"])
    am = to_am(yr)
    name = ev["name"].lower()
    notes = (ev.get("notes", "") or "").lower()
    season = ev.get("feast_season", "")

    # ── Epoch ──
    if yr < -1996:
        tags.add("#epoch.1")
    elif yr < 30:
        tags.add("#epoch.2")
    else:
        tags.add("#epoch.3")
    if yr >= 1996:
        tags.add("#epoch.overtime")

    # ── Period ──
    if yr < -2348:
        tags.add("#period.pre-flood")
    elif yr < -1921:
        tags.add("#period.post-flood")
    if -4004 <= yr < -1706:
        if yr >= -1996:
            tags.add("#period.patriarchs")
    if -1706 <= yr < -1446:
        tags.add("#period.egypt")
    if -1446 <= yr < -1406:
        tags.add("#period.wilderness")
    if -1406 <= yr < -1050:
        tags.add("#period.judges")
    if -1050 <= yr < -586:
        tags.add("#period.kingdom")
    if -586 <= yr < -516:
        tags.add("#period.exile")
    if -516 <= yr < 30:
        tags.add("#period.second-temple")
    if 30 <= yr < 313:
        tags.add("#period.early-church")
    if 313 <= yr < 1517:
        tags.add("#period.christendom")
    if 1517 <= yr < 1882:
        tags.add("#period.reformation-era")
    if 1882 <= yr < 2000:
        tags.add("#period.modern")
    if yr >= 2000:
        tags.add("#period.end-times")

    # ── Category (from keywords) ──
    cat_rules = {
        'creation': ['creation', 'adam', 'created'],
        'birth': ['born', 'birth'],
        'death': ['dies', 'death', 'martyred', 'killed', 'falls', 'massacre'],
        'judgment': ['flood', 'destroyed', 'destruction', 'plague', 'death', 'falls', 'crash', 'collapse'],
        'covenant': ['covenant', 'law', 'decree', 'accords', 'treaty', 'declaration', 'edict'],
        'war': ['war', 'battle', 'conquest', 'siege', 'revolt', 'crusade', 'invasion', 'attack', 'intifada'],
        'temple': ['temple', 'tabernacle', 'dome', 'hagia sophia', 'altar'],
        'empire': ['empire', 'crowned', 'dynasty', 'kingdom', 'conquest', 'rome', 'ottoman', 'persian'],
        'prophet': ['prophet', 'daniel', 'ezekiel', 'elijah', 'malachi', 'jeremiah', 'isaiah'],
        'patriarch': ['patriarch', 'abraham', 'isaac', 'jacob', 'noah', 'seth', 'enoch', 'adam'],
        'exodus': ['exodus', 'passover', 'sinai', 'canaan', 'jordan', 'moses'],
        'exile': ['exile', 'babylon', 'captivity', 'scattered', 'expelled', 'banned'],
        'restoration': ['restoration', 'return', 'rebuilt', 'reborn', 'recaptured', 'aliyah'],
        'reformation': ['reform', 'luther', 'theses', 'protestant', 'bible', 'printing', 'translation', 'gutenberg', 'wycliffe', 'king james'],
        'persecution': ['persecution', 'holocaust', 'kristallnacht', 'pogrom', 'inquisition'],
        'translation': ['translated', 'translation', 'taken', 'enoch'],
        'schism': ['schism', 'divides', 'splits'],
        'messianic': ['jesus', 'christ', 'crucifixion', 'resurrection', 'baptized', 'jubilee.*luke', 'magi'],
        'islamic': ['muhammad', 'muslim', 'islam', 'hijra', 'mecca', 'medina', 'ottoman', 'caliphate', 'vienna', 'tours'],
        'zionist': ['zionist', 'aliyah', 'balfour', 'mandate', 'israel reborn', 'six-day', 'jerusalem'],
        'apocalyptic': ['revelation', '666', 'beast', 'end times', 'convergence', 'shemitah'],
    }
    for cat, keywords in cat_rules.items():
        for kw in keywords:
            if re.search(kw, name) or re.search(kw, notes):
                tags.add(f"#cat.{cat}")
                break

    # ── Nation/People ──
    nation_rules = {
        'israel': ['israel', 'jewish', 'jews', 'hebrew', 'judah', 'judea', 'zion', 'jerusalem', 'canaan', 'sinai', 'temple'],
        'egypt': ['egypt', 'pharaoh', 'exodus', 'sojourn'],
        'babylon': ['babylon', 'nebuchadnezzar', 'chaldean'],
        'persia': ['persia', 'cyrus', 'artaxerxes', 'mede'],
        'greece': ['greek', 'alexander', 'septuagint', 'hellenist'],
        'rome': ['rome', 'roman', 'caesar', 'titus', 'pompey', 'constantine', 'nicaea', 'latin'],
        'islam': ['muslim', 'islam', 'muhammad', 'ottoman', 'caliphate', 'mecca', 'medina', 'hijra', 'dome', 'arab'],
        'church': ['church', 'christian', 'protestant', 'catholic', 'pope', 'council', 'creed', 'monastery'],
        'britain': ['british', 'england', 'english', 'anglo', 'balfour', 'mandate', 'norman', 'alfred', 'magna carta', 'king james'],
        'america': ['america', 'columbus', 'puritan', 'independence', 'massachusetts'],
        'russia': ['russia', 'soviet', 'ukraine', 'vladimir', 'kievan'],
        'germany': ['german', 'luther', 'nazi', 'reichstag', 'augsburg', 'kristallnacht', 'thirty years'],
    }
    for nation, keywords in nation_rules.items():
        for kw in keywords:
            if re.search(kw, name, re.I) or re.search(kw, notes, re.I):
                tags.add(f"#nation.{nation}")
                break

    # ── Feast connection ──
    if season == 'spring':
        tags.add("#feast.spring")
    if season == 'fall':
        tags.add("#feast.fall")
    feast_rules = {
        'passover': ['passover', 'nisan', '14 nisan', 'pesach'],
        'pentecost': ['pentecost', 'shavuot', 'weeks'],
        'tabernacles': ['tabernacles', 'sukkot', 'booths'],
        'yom-kippur': ['yom kippur', 'atonement', 'tishri 10'],
        'rosh-hashanah': ['rosh hashanah', 'trumpets', 'tishri 1'],
        'tisha-bav': ['tisha', 'av', '9th of av'],
        'hanukkah': ['hanukkah', 'rededication', 'maccabean'],
        'purim': ['purim', 'esther'],
    }
    for feast, keywords in feast_rules.items():
        for kw in keywords:
            if re.search(kw, name, re.I) or re.search(kw, notes, re.I):
                tags.add(f"#feast.{feast}")
                break

    # ── Clock ──
    tags.add("#clock.cosmic")
    tags.add("#clock.moadim")
    if yr >= -1406:
        tags.add("#clock.israel")
    if yr >= 26:
        tags.add("#clock.church")
    if yr >= -457:
        tags.add("#clock.daniel")

    # ── Signature ──
    if db_row and db_row.get("signature"):
        sig_name = db_row["signature"].lower().replace(' ', '-').replace('/', '-')
        tags.add(f"#sig.{sig_name}")

    # ── Theme ──
    theme_rules = {
        'jerusalem': ['jerusalem', 'zion', 'temple mount', 'dome'],
        'temple': ['temple', 'tabernacle', 'sanctuary'],
        'exile': ['exile', 'captivity', 'babylon', 'scattered', 'expelled', 'deported'],
        'return': ['return', 'restored', 'rebuilt', 'reborn', 'aliyah', 'recaptured'],
        'messiah': ['jesus', 'christ', 'messiah', 'anointed', 'magi'],
        'redemption': ['redeem', 'passover', 'lamb', 'blood', 'salvation'],
        'law': ['law', 'sinai', 'torah', 'commandment', 'constitution', 'code'],
        'grace': ['grace', 'pentecost', 'spirit', 'church'],
        'gentiles': ['gentile', 'nations', 'rome', 'greece', 'babylon', 'persian', 'ottoman'],
        'judgment': ['judgment', 'destroyed', 'flood', 'fire', 'plague', 'crash', 'wrath'],
        'prophecy': ['prophecy', 'prophetic', 'daniel', 'revelation', 'ezekiel', 'isaiah', 'vision', '70 weeks'],
        'scripture': ['bible', 'scroll', 'scripture', 'translation', 'vulgate', 'gutenberg', 'wycliffe', 'septuagint'],
        'kingdom': ['kingdom', 'king', 'emperor', 'crowned', 'dynasty', 'empire', 'throne'],
        'persecution': ['persecution', 'martyr', 'holocaust', 'pogrom', 'crusade', 'inquisition'],
        'peace': ['peace', 'accords', 'treaty', 'armistice'],
        'war': ['war', 'battle', 'invasion', 'siege', 'attack', 'revolt'],
    }
    for theme, keywords in theme_rules.items():
        for kw in keywords:
            if re.search(kw, name, re.I) or re.search(kw, notes, re.I):
                tags.add(f"#theme.{theme}")
                break

    # ── Pattern ──
    if '.42' in notes or '0.42' in notes or '.4200' in notes:
        tags.add("#pattern.42-chain")
    if '.68' in notes or 'cross' in notes.lower():
        tags.add("#pattern.cross-signature")
    if '.48' in notes or 'worship-shutdown' in notes.lower() or 'worship shutdown' in notes.lower():
        tags.add("#pattern.worship-shutdown")
    if 'shemitah' in notes.lower() or 'sabbatical' in notes.lower():
        tags.add("#pattern.shemitah")
    if '.666' in notes or '.66' in notes:
        tags.add("#pattern.666-warning")
    if 'tisha' in notes.lower() or '9th of av' in notes.lower():
        tags.add("#pattern.tisha-bav")
    if am % 1000 < 10 or am % 1000 > 990:
        tags.add("#pattern.am-milestone")
    if '.0000' in notes or 'exact' in notes.lower():
        tags.add("#pattern.exact-jubilee")
    if 'anchor' in notes.lower():
        tags.add("#pattern.anchor-date")

    # ── Sacred numbers (from gap to next event) ──
    # These get applied at the index level, not per-event

    return sorted(tags)

def main():
    parser = argparse.ArgumentParser(description='Auto-enrich events with hierarchical tags')
    parser.add_argument('--dry-run', action='store_true', help='Print tags without writing')
    parser.add_argument('--event', help='Show tags for a specific event')
    parser.add_argument('--stats', action='store_true', help='Show tag statistics only')
    args = parser.parse_args()

    events = load_events()
    db_rows = load_database()

    # Build lookup by name
    db_lookup = {r["name"]: r for r in db_rows}

    # Check if tags column exists
    fieldnames = list(events[0].keys())
    if 'tags' not in fieldnames:
        fieldnames.append('tags')

    # Enrich
    total_tags = 0
    tag_counts = defaultdict(int)
    for ev in events:
        db_row = db_lookup.get(ev["name"])
        tags = auto_tag(ev, db_row)
        ev["tags"] = ' '.join(tags)
        total_tags += len(tags)
        for t in tags:
            root = '#' + t.lstrip('#').split('.')[0]
            tag_counts[root] += 1

    if args.event:
        matches = [e for e in events if args.event.lower() in e["name"].lower()]
        for e in matches:
            print(f"\n{e['name']} ({e['year_ad']}):")
            for t in e['tags'].split():
                print(f"  {t}")
        return

    if args.stats:
        print(f"\nTag Statistics:")
        print(f"  Events: {len(events)}")
        print(f"  Total tags assigned: {total_tags}")
        print(f"  Avg tags/event: {total_tags/len(events):.1f}")
        print(f"\n  By root category:")
        for root in sorted(tag_counts.keys()):
            print(f"    {root}: {tag_counts[root]} assignments")
        return

    if args.dry_run:
        for ev in events[:10]:
            print(f"\n{ev['name']}:")
            print(f"  {ev['tags']}")
        print(f"\n... ({len(events)} total events)")
        return

    # Write enriched events.csv
    with open(DATA / "events.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(events)

    print(f"\nEnriched {len(events)} events with tags")
    print(f"  Total tags assigned: {total_tags}")
    print(f"  Avg tags/event: {total_tags/len(events):.1f}")
    print(f"\n  By root category:")
    for root in sorted(tag_counts.keys()):
        print(f"    {root}: {tag_counts[root]} assignments")

if __name__ == "__main__":
    main()
