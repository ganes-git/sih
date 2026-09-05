#!/usr/bin/env python3
"""
slop_check.py — DESIGN.md compliance checker for /frontend
Stage 7 self-verification tool.

Greps every .html, .css, and .js file in /frontend for patterns that violate
the locked design contract in DESIGN.md. If any match is found, the file path,
line number, and matched content are printed and the script exits with code 1.

Banned patterns checked:
  1. "gradient"           — no CSS gradients of any kind
  2. "backdrop-filter"    — no glassmorphism blur
  3. "Inter"              — deliberate use of Inter font is banned (fallback is fine)
  4. cubic-bezier with overshoot (third value > 1 or < 0) — no bounce/spring/elastic curves
  5. Blue/indigo/purple hex colours — #[4-9a-f][0-9a-f]{4}  (rough blue-range heuristic)
     More precisely: hues in ~180-300° range in hex:
       #[0-9a-f]{2}[0-9a-f]{2}[ef][0-9a-f]{2}  (high blue component, low red)
     We use a set of known-bad prefixes for common blue/indigo/purple shades.
  6. border-radius > 4px — any pixel value above 4
  7. "box-shadow"         — no drop shadows
"""

import re
import sys
import os
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent  # /frontend
EXTENSIONS = {".html", ".css", ".js"}

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

RULES = []

# 1. Any gradient usage
RULES.append({
    "name": "gradient",
    "pattern": re.compile(r"gradient", re.IGNORECASE),
    "description": "CSS gradients are banned (DESIGN.md: no gradients of any kind)",
})

# 2. backdrop-filter (glassmorphism)
RULES.append({
    "name": "backdrop-filter",
    "pattern": re.compile(r"backdrop-filter", re.IGNORECASE),
    "description": "backdrop-filter is banned (DESIGN.md: no glassmorphism)",
})

# 3. Deliberate Inter font
RULES.append({
    "name": "Inter font",
    "pattern": re.compile(r"""\bInter\b"""),
    "description": "Inter must not be named in any font stack (DESIGN.md)",
})

# 4. cubic-bezier with overshoot: third param > 1 or second param < 0
# Matches cubic-bezier(a, b, c, d) where c > 1.0 or b < 0
RULES.append({
    "name": "cubic-bezier overshoot",
    "pattern": re.compile(
        r"cubic-bezier\(\s*[\d.]+\s*,\s*(-[\d.]+)\s*,\s*[\d.]+\s*,\s*[\d.]+\s*\)|"
        r"cubic-bezier\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*(1\.[1-9]\d*|[2-9][\d.]*)\s*,\s*[\d.]+\s*\)",
        re.IGNORECASE
    ),
    "description": "Elastic/spring cubic-bezier curves are banned (DESIGN.md: no bounce/overshoot)",
})

# 5. Blue/indigo/purple hex colours — common ranges
# Checking for hex values that look like blue/indigo/purple:
# These are sampled known patterns; we flag anything with high blue, low red channel
BLUE_PURPLE_PATTERN = re.compile(
    r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b",
)

def is_blue_indigo_purple(hex_val):
    """Return True if the hex colour falls in the blue/indigo/purple family."""
    h = hex_val.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    if len(h) != 6:
        return False
    try:
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
    except ValueError:
        return False
    # Blue-dominant: b significantly exceeds r, and hue is in blue/indigo/purple range
    # Rough check: b >= 160 and b > r * 1.5 and (g < r * 1.3 or b > g * 1.3)
    if b >= 150 and b > r * 1.4:
        return True
    # Purple: r and b both high, g low
    if r >= 100 and b >= 100 and g < 100 and abs(r - b) < 80:
        return True
    return False

RULES.append({
    "name": "blue/indigo/purple colour",
    "pattern": BLUE_PURPLE_PATTERN,
    "description": "Blue/indigo/purple hex colours are banned (DESIGN.md palette)",
    "filter": is_blue_indigo_purple,
})

# 6. border-radius > 4px
BORDER_RADIUS_PATTERN = re.compile(r"border-radius\s*:\s*([^\n;]+)", re.IGNORECASE)

def has_radius_over_4px(match_str):
    """Return True if any px value in the border-radius declaration exceeds 4."""
    values = re.findall(r"(\d+(?:\.\d+)?)px", match_str)
    return any(float(v) > 4.0 for v in values)

RULES.append({
    "name": "border-radius > 4px",
    "pattern": BORDER_RADIUS_PATTERN,
    "description": "border-radius must not exceed 4px (DESIGN.md)",
    "filter": has_radius_over_4px,
})

# 7. box-shadow (drop shadows)
RULES.append({
    "name": "box-shadow",
    "pattern": re.compile(r"box-shadow\s*:", re.IGNORECASE),
    "description": "box-shadow (drop shadows) is banned (DESIGN.md)",
})

# ---------------------------------------------------------------------------
# Allowed palette — these hex values are permitted; skip if seen
# ---------------------------------------------------------------------------
ALLOWED_HEX = {
    "#fafaf8", "#1f1f1f", "#6b6b63", "#e1ded6",
    "#2f5233", "#c98a1e", "#b3262a",
    "#243f27",  # hover shade of accent
    "#f0ede8", "#f5f3ef",  # hover/bg shades
    "#ffffff", "#fff",
}

# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

def check_file(filepath: Path) -> list:
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [{"file": str(filepath), "line": 0, "rule": "read error", "match": str(e)}]

    lines = content.splitlines()

    for lineno, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("/*") or stripped.startswith("//") or stripped.startswith("*"):
            continue

        for rule in RULES:
            pattern = rule["pattern"]
            filt = rule.get("filter")

            for m in pattern.finditer(line):
                matched_text = m.group(0)

                # For hex colour rule, skip allowed palette entries
                if rule["name"] == "blue/indigo/purple colour":
                    if matched_text.lower() in ALLOWED_HEX:
                        continue
                    if not filt(matched_text):
                        continue

                # For border-radius and cubic-bezier, apply filter
                if filt and rule["name"] not in ("blue/indigo/purple colour",):
                    if not filt(matched_text):
                        continue

                violations.append({
                    "file": str(filepath.relative_to(FRONTEND_DIR.parent)),
                    "line": lineno,
                    "rule": rule["name"],
                    "description": rule["description"],
                    "match": matched_text.strip()[:80],
                })

    return violations


def main():
    all_violations = []

    for ext in EXTENSIONS:
        for filepath in sorted(FRONTEND_DIR.rglob(f"*{ext}")):
            # Skip tools/ itself
            if "tools" in filepath.parts:
                continue
            violations = check_file(filepath)
            all_violations.extend(violations)

    if all_violations:
        print(f"\nSLOP CHECK: {len(all_violations)} violation(s) found.\n")
        print(f"{'FILE':<45} {'LINE':>5}  {'RULE':<30}  MATCH")
        print("-" * 120)
        for v in all_violations:
            print(f"{v['file']:<45} {v['line']:>5}  {v['rule']:<30}  {v['match']}")
        print()
        sys.exit(1)
    else:
        print(f"SLOP CHECK: 0 violations. All {sum(1 for ext in EXTENSIONS for _ in FRONTEND_DIR.rglob(f'*{ext}'))} frontend files are clean.")
        sys.exit(0)


if __name__ == "__main__":
    main()
