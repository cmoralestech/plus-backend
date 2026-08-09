"""Make every seed profile's name and occupation unique.

Fifteen first names and eighteen occupations were shared, always across the two
markets. Discovery is now radius-scoped so a single member never sees both
halves of a pair, but the duplication is still visible to anyone browsing by
city, and to us.

Where a pair spans both cities the Houston side is changed: Miami holds every
real member, so leaving those names stable avoids confusing anyone who has
already browsed. The one same-city pair (two Miami architects) is resolved by
narrowing the junior of the two.

New occupations are narrower versions of the same job rather than different
jobs, so the bio, headline and prompts written for that person still fit. A
cardiologist becoming an interventional cardiologist keeps their words true; a
cardiologist becoming a florist does not.

Usage:
    python seed_unique.py [--dry-run]
"""
import argparse
import asyncio
import sys

from sqlalchemy import select

from app.database import async_session
from app.models.profile import Profile

# id: new display_name. Every one of these is the Houston half of a cross-market
# pair, and none collides with an existing name in either city.
NAMES = {
    112: "Desmond",    # was Andre    (Miami keeps Andre, commercial pilot)
    148: "Lorraine",   # was Angela
    160: "Errol",      # was Bill
    106: "Gus",        # was Curtis
    142: "Yvette",     # was Denise
    171: "Darnell",    # was Deshawn
    166: "Roy",        # was Frank
    141: "Cheryl",     # was Grace
    140: "Wade",       # was Hank
    153: "Jaylen",     # was Malik
    184: "Samir",      # was Omar
    200: "Dwayne",     # was Paul
    117: "Anjali",     # was Priya
    180: "Chuck",      # was Rick
    109: "Marisela",   # was Rosa
}

# id: new occupation. Narrowed, not replaced — see the module docstring.
OCCUPATIONS = {
    87: "Landscape architect",              # was Architect (Miami/Miami pair)
    110: "Interventional cardiologist",     # was Cardiologist
    120: "Industrial real estate",          # was Commercial real estate
    155: "Orthodontic assistant",           # was Dental hygienist
    127: "Commercial interior designer",    # was Interior designer
    159: "Grill cook",                      # was Line cook
    199: "Nursing student, final year",     # was Nursing student
    195: "Paediatric occupational therapist",  # was Occupational therapist
    170: "Owns a signage business",         # was Owns a printing business
    169: "Strength coach",                  # was Personal trainer
    113: "Hospital pharmacist",             # was Pharmacist
    145: "Neurological physiotherapist",    # was Physiotherapist (one of three)
    201: "Paediatric physiotherapist",      # was Physiotherapist (one of three)
    122: "Runs a civil engineering firm",   # was Runs a construction firm
    112: "Runs a freight brokerage",        # was Runs a logistics firm
    125: "Medical social worker",           # was Social worker
    117: "Embedded software engineer",      # was Software engineer
    181: "Live sound engineer",             # was Sound engineer
}


async def run(dry_run: bool) -> int:
    ids = set(NAMES) | set(OCCUPATIONS)

    async with async_session() as db:
        rows = (await db.execute(select(Profile).where(Profile.id.in_(ids)))).scalars().all()
        found = {p.id: p for p in rows}

        missing = ids - set(found)
        if missing:
            print(f"  warning: no profile for ids {sorted(missing)}")

        renamed = retitled = 0
        for pid in sorted(ids):
            p = found.get(pid)
            if not p:
                continue
            if not p.is_seed:
                print(f"  SKIPPED {pid}: not a seed profile — refusing to rename a real member")
                continue

            if pid in NAMES:
                old = p.display_name
                new = NAMES[pid]
                # A name written into that profile's own prose would be left
                # stranded by the rename, which reads worse than the duplicate
                # it fixes.
                for field in ("bio", "headline", "looking_for", "ideal_first_date", "offering"):
                    text = getattr(p, field, None)
                    if text and old and old in text:
                        print(f"  NOTE {pid}: '{old}' appears in {field} — check after rename")
                print(f"  {pid}: {old} → {new}")
                p.display_name = new
                renamed += 1

            if pid in OCCUPATIONS:
                print(f"  {pid}: {p.occupation} → {OCCUPATIONS[pid]}")
                p.occupation = OCCUPATIONS[pid]
                retitled += 1

        if dry_run:
            print(f"\n  would rename {renamed}, retitle {retitled} (dry run, nothing written)")
            await db.rollback()
            return 0

        await db.commit()
        print(f"\n  renamed {renamed}, retitled {retitled}")

    # Prove the goal rather than assume it: a partial apply would otherwise look
    # like a success.
    async with async_session() as db:
        for column in ("display_name", "occupation"):
            total = (await db.execute(
                select(Profile).where(Profile.is_seed == True)  # noqa: E712
            )).scalars().all()
            values = [getattr(p, column) for p in total]
            print(f"  {column}: {len(set(values))} distinct of {len(values)}")

    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()
    return await run(args.dry_run)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
