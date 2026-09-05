"""
Multi-Modal Identity Fusion & Trajectory Matching Engine (Stage 4)

This module fuses three complementary signals into a single unified identity score:
1. Plate Text Similarity (Levenshtein ratio on clean plate strings)
2. Visual Appearance Similarity (Cosine similarity of 512-D OpenCLIP embeddings)
3. Spatio-Temporal Transit Plausibility (Haversine GPS distance vs elapsed time)

ROBUSTNESS PLUMBING CONTEXT:
---------------------------
This module is the plumbing that keeps vehicle identity continuous across cameras when plate
recognition fails (e.g. motion blur, occlusion, low-light underpasses) or detects cloned plates
(identical plate strings on visually disparate vehicles). It provides reliable trajectory continuity
for the route-anomaly engine built in Stage 5.

WEIGHTING AND SCORING FORMULAS:
-------------------------------
1. Plate Score:
     S_plate = Levenshtein.ratio(plate_a, plate_b) if (both plates confirmed) else 0.0

2. Visual Score:
     S_visual = CosineSimilarity(embedding_a, embedding_b) in [0.0, 1.0]

3. Transit Plausibility Score:
     Computes implied speed v = distance_km / delta_hours.
     - If v <= MAX_CITY_SPEED_KMH (90.0 km/h): S_transit = 1.0
     - If v > 90.0 km/h: S_transit = exp(- (v - 90)^2 / (2 * 25^2))  (decays toward 0)

4. Composite Score:
     - Case A (Both plates confirmed):
         S_base = 0.65 * S_plate + 0.35 * S_visual
     - Case B (Either plate unconfirmed / degraded):
         S_base = S_visual  (Visual appearance carries 100% of identity)

     Final Gated Score:
         S_composite = S_base * S_transit

5. Cloned Plate Detection:
     clone_flag = (S_plate >= CLONE_PLATE_MIN_THRESH [0.88]) and (S_visual < CLONE_VISUAL_MAX_THRESH [0.60])
"""

import math
import re
from typing import Dict, Any, Tuple, Optional
import Levenshtein

from pipeline.sighting import Sighting
from pipeline.embed import compute_cosine_similarity

# Constants
MAX_CITY_SPEED_KMH: float = 90.0         # Realistic maximum urban arterial speed (km/h)
SPEED_FALLOFF_SIGMA: float = 25.0        # Rate of plausibility decay for speeds above threshold
CLONE_PLATE_MIN_THRESH: float = 0.88     # Plate match threshold to test for vehicle cloning
CLONE_VISUAL_MAX_THRESH: float = 0.60    # Maximum visual similarity allowed before flagging as clone
CONFIRMATION_MATCH_THRESH: float = 0.65  # Composite score required to confirm cross-camera identity match


def _get_attr(obj: Any, attr: str, default: Any = None) -> Any:
    """Helper to extract attribute from either a Sighting Pydantic model or a dictionary."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def clean_plate_string(text: Optional[str]) -> str:
    """Normalize plate text by stripping whitespace, hyphens, and non-alphanumeric characters."""
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(text).upper().strip())


def plate_score(sighting_a: Any, sighting_b: Any) -> float:
    """
    Compute fuzzy string similarity between two sightings' plate texts using Levenshtein ratio.
    Returns 0.0 if either sighting has no confirmed plate text.
    Accepts Sighting objects, dicts, or raw plate strings.
    """
    text_a = sighting_a if isinstance(sighting_a, str) else _get_attr(sighting_a, "plate_text")
    text_b = sighting_b if isinstance(sighting_b, str) else _get_attr(sighting_b, "plate_text")

    if not text_a or not text_b:
        return 0.0

    unconf_a = False if isinstance(sighting_a, str) else bool(_get_attr(sighting_a, "unconfirmed_plate", False))
    unconf_b = False if isinstance(sighting_b, str) else bool(_get_attr(sighting_b, "unconfirmed_plate", False))
    if unconf_a or unconf_b:
        return 0.0

    str_a = clean_plate_string(text_a)
    str_b = clean_plate_string(text_b)

    if not str_a or not str_b:
        return 0.0

    return float(Levenshtein.ratio(str_a, str_b))


def visual_score(sighting_a: Any, sighting_b: Any) -> float:
    """
    Compute cosine similarity between two sightings' OpenCLIP visual appearance embeddings.
    Accepts Sighting objects, dicts, or raw embedding lists.
    """
    emb_a = sighting_a if isinstance(sighting_a, list) else _get_attr(sighting_a, "embedding")
    emb_b = sighting_b if isinstance(sighting_b, list) else _get_attr(sighting_b, "embedding")

    if emb_a is None or emb_b is None:
        return 0.0

    if isinstance(emb_a, str):
        try:
            emb_a = json.loads(emb_a)
        except Exception:
            return 0.0
    if isinstance(emb_b, str):
        try:
            emb_b = json.loads(emb_b)
        except Exception:
            return 0.0

    return compute_cosine_similarity(emb_a, emb_b)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two GPS coordinates using the Haversine formula."""
    r_earth = 6371.0  # Earth's mean radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r_earth * c


def transit_score(sighting_a: Any, sighting_b: Any) -> Tuple[float, Dict[str, Any]]:
    """
    Compute spatio-temporal transit plausibility based on GPS distance and elapsed time.
    Returns (score, details) where score is in [0.0, 1.0].
    """
    lat_a = float(_get_attr(sighting_a, "lat", 0.0))
    lon_a = float(_get_attr(sighting_a, "lon", 0.0))
    lat_b = float(_get_attr(sighting_b, "lat", 0.0))
    lon_b = float(_get_attr(sighting_b, "lon", 0.0))

    t_a = float(_get_attr(sighting_a, "timestamp", 0.0))
    t_b = float(_get_attr(sighting_b, "timestamp", 0.0))

    dist_km = haversine_distance_km(lat_a, lon_a, lat_b, lon_b)
    time_delta_sec = abs(t_b - t_a)
    time_delta_hours = time_delta_sec / 3600.0

    # Same location check
    if dist_km < 0.05:  # Within 50 meters
        return 1.0, {
            "distance_km": round(dist_km, 3),
            "time_delta_sec": round(time_delta_sec, 1),
            "implied_speed_kmh": 0.0,
            "is_plausible": True,
        }

    # Zero or sub-second elapsed time with significant distance -> impossible teleportation
    if time_delta_hours < (1.0 / 3600.0):
        return 0.0, {
            "distance_km": round(dist_km, 3),
            "time_delta_sec": round(time_delta_sec, 1),
            "implied_speed_kmh": 9999.0,
            "is_plausible": False,
        }

    implied_speed_kmh = dist_km / time_delta_hours

    if implied_speed_kmh <= MAX_CITY_SPEED_KMH:
        score = 1.0
    else:
        # Smooth Gaussian decay for speeds exceeding realistic city thresholds
        overshoot = implied_speed_kmh - MAX_CITY_SPEED_KMH
        score = math.exp(- (overshoot ** 2) / (2.0 * (SPEED_FALLOFF_SIGMA ** 2)))

    score = max(0.0, min(1.0, score))
    return round(score, 4), {
        "distance_km": round(dist_km, 3),
        "time_delta_sec": round(time_delta_sec, 1),
        "implied_speed_kmh": round(implied_speed_kmh, 1),
        "is_plausible": score >= 0.50,
    }


def clone_flag(sighting_a: Any, sighting_b: Any) -> bool:
    """
    Identifies cloned / tampered plates.
    Returns True when plate texts match identically,
    but visual appearance embeddings differ significantly (< 0.60).
    """
    text_a = _get_attr(sighting_a, "plate_text")
    text_b = _get_attr(sighting_b, "plate_text")
    if not text_a or not text_b:
        return False

    unconf_a = bool(_get_attr(sighting_a, "unconfirmed_plate", False))
    unconf_b = bool(_get_attr(sighting_b, "unconfirmed_plate", False))
    if unconf_a or unconf_b:
        return False

    clean_a = clean_plate_string(text_a)
    clean_b = clean_plate_string(text_b)
    if not clean_a or clean_a != clean_b:
        return False

    s_visual = visual_score(sighting_a, sighting_b)
    return s_visual < CLONE_VISUAL_MAX_THRESH


def composite_score(
    sighting_a: Any,
    sighting_b: Any,
    enforce_transit: bool = True,
) -> Dict[str, Any]:
    """
    Fuses plate text, visual appearance, and transit plausibility into a composite identity score.

    Returns:
        Dict with composite_score, component scores, match decision, and clone alert flag.
    """
    s_plate = plate_score(sighting_a, sighting_b)
    s_visual = visual_score(sighting_a, sighting_b)
    s_transit, transit_details = transit_score(sighting_a, sighting_b)

    text_a = _get_attr(sighting_a, "plate_text")
    text_b = _get_attr(sighting_b, "plate_text")
    unconf_a = bool(_get_attr(sighting_a, "unconfirmed_plate", False))
    unconf_b = bool(_get_attr(sighting_b, "unconfirmed_plate", False))

    has_both_plates = (
        text_a is not None
        and text_b is not None
        and not unconf_a
        and not unconf_b
    )

    if has_both_plates:
        # Dual confirmed plates: plate similarity carries 65%, visual carries 35%
        s_base = 0.65 * s_plate + 0.35 * s_visual
        regime = "DUAL_PLATE_AND_VISUAL"
    else:
        # Either plate unconfirmed / degraded: visual embedding carries 100%
        s_base = s_visual
        regime = "VISUAL_REID_DOMINATED"

    # Transit gate multiplier: physically implausible transit pulls composite score down
    transit_multiplier = s_transit if enforce_transit else 1.0
    s_composite = s_base * transit_multiplier

    # Clone plate alert check
    is_clone = clone_flag(sighting_a, sighting_b)
    is_match = (s_composite >= CONFIRMATION_MATCH_THRESH) and not is_clone

    return {
        "composite_score": round(s_composite, 4),
        "plate_score": round(s_plate, 4),
        "visual_score": round(s_visual, 4),
        "transit_score": round(s_transit, 4),
        "regime": regime,
        "is_match": is_match,
        "clone_flag": is_clone,
        "has_both_plates": has_both_plates,
        "transit_details": transit_details,
    }
