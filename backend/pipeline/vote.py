"""
Multi-Frame Confidence Voting & Indian Plate Syntax Repair Module (Stage 3)

This module aggregates raw OCR predictions across sampled video frames for a vehicle,
normalises candidate strings, executes a syntax-aware character repair pass for Indian plates,
and calculates a multi-frame confidence score to decide between confirmation and rejection.

CONFIDENCE FORMULA & DECISION RULE:
-----------------------------------
Given candidate plate string S with k frame votes, individual OCR confidence scores {c_1, ..., c_k},
and N total valid frame readings:

  1. Average OCR Confidence:
       avg_conf(S) = (1 / k) * sum_{i=1}^k c_i

  2. Vote Frequency / Agreement:
       vote_share(S) = k / N

  3. Multi-Frame Consistency Multiplier:
       consistency(S) = min(1.0, k / MIN_REQUIRED_VOTES)   [where MIN_REQUIRED_VOTES = 2]

  4. Aggregate Confidence Score:
       Score(S) = avg_conf(S) * (0.65 * vote_share(S) + 0.35 * consistency(S)) * syntax_bonus

Decision Rule:
  If top candidate Score(S) >= MIN_CONFIDENCE_THRESHOLD (0.50), k >= MIN_REQUIRED_VOTES (2),
  and candidate resolves to a valid Indian plate syntax:
      Confirm: plate_text = S, unconfirmed = False
  Else:
      Reject:  plate_text = None, unconfirmed = True
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict

MIN_CONFIDENCE_THRESHOLD = 0.50
MIN_REQUIRED_VOTES = 2

# Standard Indian State and Union Territory 2-letter prefixes
INDIAN_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CH", "CG", "DD", "DL", "DN",
    "GA", "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD",
    "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ",
    "SK", "TN", "TR", "TS", "UK", "UP", "WB", "BH",
}

# Standard Indian vehicle registration regex
# e.g. TN07AB1234, DL01EF9012, MH12CD5678, KA05GH3456
INDIAN_PLATE_REGEX = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$")

# Optical Character Confusion Mappings
LETTER_TO_DIGIT = {
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1", "T": "1",
    "Z": "2",
    "S": "5",
    "B": "8",
    "G": "6",
}

DIGIT_TO_LETTER = {
    "0": "O",
    "1": "I",
    "2": "Z",
    "5": "S",
    "8": "B",
    "6": "G",
}


def clean_raw_ocr_text(text: str) -> str:
    """Uppercase and strip all whitespace and non-alphanumeric characters."""
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]", "", text.upper().strip())


def is_valid_indian_plate(text: str) -> bool:
    """Check whether a cleaned string satisfies Indian license plate formatting rules."""
    if not text or len(text) < 7 or len(text) > 11:
        return False
    if not INDIAN_PLATE_REGEX.match(text):
        return False
    state_code = text[:2]
    return state_code in INDIAN_STATE_CODES or state_code.isalpha()


def attempt_indian_plate_repair(text: str) -> Optional[str]:
    """
    Apply rule-based correction for OCR character confusions (0<->O, 1<->I, 8<->B, S<->5)
    ONLY when the repair resolves the string to a valid Indian license plate pattern.

    Standard Structure:
      [State: 2 letters] + [District: 1-2 digits] + [Series: 0-3 letters] + [Registration: 4 digits]
    """
    cleaned = clean_raw_ocr_text(text)
    if not cleaned or len(cleaned) < 7:
        return None

    # If already valid, retain as-is
    if is_valid_indian_plate(cleaned):
        return cleaned

    chars = list(cleaned)
    n = len(chars)

    if n >= 8:
        # 1. First 2 characters must be State letters
        for i in range(2):
            if chars[i].isdigit() and chars[i] in DIGIT_TO_LETTER:
                chars[i] = DIGIT_TO_LETTER[chars[i]]

        # 2. Last 4 characters must be numeric registration digits
        for i in range(n - 4, n):
            if chars[i].isalpha() and chars[i] in LETTER_TO_DIGIT:
                chars[i] = LETTER_TO_DIGIT[chars[i]]

        # 3. Middle district / series positions
        if n == 10:
            # Format: LL DD LL DDDD (e.g. TN07AB1234)
            for i in (2, 3):
                if chars[i].isalpha() and chars[i] in LETTER_TO_DIGIT:
                    chars[i] = LETTER_TO_DIGIT[chars[i]]
            for i in (4, 5):
                if chars[i].isdigit() and chars[i] in DIGIT_TO_LETTER:
                    chars[i] = DIGIT_TO_LETTER[chars[i]]

        elif n == 9:
            # Format: LL D LL DDDD or LL DD L DDDD
            if chars[2].isalpha() and chars[2] in LETTER_TO_DIGIT:
                chars[2] = LETTER_TO_DIGIT[chars[2]]
            if chars[3].isdigit() and chars[4].isdigit() and chars[4] in DIGIT_TO_LETTER:
                chars[4] = DIGIT_TO_LETTER[chars[4]]

    repaired = "".join(chars)
    if is_valid_indian_plate(repaired):
        return repaired

    return None


def format_plate_display(cleaned_plate: str) -> str:
    """Format normalised string with canonical spacing (e.g. 'TN 07 AB 1234')."""
    if not cleaned_plate:
        return ""
    if len(cleaned_plate) == 10:
        return f"{cleaned_plate[:2]} {cleaned_plate[2:4]} {cleaned_plate[4:6]} {cleaned_plate[6:]}"
    if len(cleaned_plate) == 9:
        return f"{cleaned_plate[:2]} {cleaned_plate[2:4]} {cleaned_plate[4:5]} {cleaned_plate[5:]}"
    return cleaned_plate


def vote_on_readings(
    ocr_readings: List[Dict[str, Any]],
    min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
    min_votes: int = MIN_REQUIRED_VOTES,
) -> Dict[str, Any]:
    """
    Multi-frame confidence voting over raw OCR readings for a vehicle.

    Returns:
        Dict with:
        - 'plate_text': Formatted confirmed plate string or None
        - 'confidence': Aggregate confidence score (0.0 to 1.0)
        - 'unconfirmed': Boolean flag (True if rejected or below threshold)
        - 'best_candidate_raw': Raw normalised candidate string
        - 'vote_count': Number of frame votes for winner
        - 'total_readings': Total valid candidate readings evaluated
        - 'vote_summary': Per-candidate score breakdown
    """
    if not ocr_readings:
        return {
            "plate_text": None,
            "confidence": 0.0,
            "unconfirmed": True,
            "reason": "No OCR text detected across frames",
            "best_candidate_raw": None,
            "vote_count": 0,
            "total_readings": 0,
            "vote_summary": {},
        }

    candidate_scores = defaultdict(list)
    total_valid_readings = 0

    for item in ocr_readings:
        raw_text = item.get("raw_text", "")
        ocr_conf = float(item.get("ocr_confidence", 0.0))

        cleaned = clean_raw_ocr_text(raw_text)
        repaired = attempt_indian_plate_repair(cleaned)

        resolved_key = repaired if repaired else (cleaned if len(cleaned) >= 5 else None)
        if resolved_key:
            candidate_scores[resolved_key].append(ocr_conf)
            total_valid_readings += 1

    if not candidate_scores or total_valid_readings == 0:
        return {
            "plate_text": None,
            "confidence": 0.0,
            "unconfirmed": True,
            "reason": "No candidate resolved to plausible plate syntax",
            "best_candidate_raw": None,
            "vote_count": 0,
            "total_readings": len(ocr_readings),
            "vote_summary": {},
        }

    vote_summary = {}
    best_candidate = None
    best_score = -1.0

    for candidate, conf_list in candidate_scores.items():
        k = len(conf_list)
        avg_conf = sum(conf_list) / float(k)
        vote_share = k / float(total_valid_readings)
        consistency = min(1.0, k / float(min_votes))

        # Core Confidence Formula
        score = avg_conf * (0.65 * vote_share + 0.35 * consistency)

        # Syntax validity multiplier
        if is_valid_indian_plate(candidate):
            score = min(1.0, score * 1.05)

        vote_summary[candidate] = {
            "vote_count": k,
            "avg_ocr_conf": round(avg_conf, 4),
            "vote_share": round(vote_share, 4),
            "final_score": round(score, 4),
            "is_valid_format": is_valid_indian_plate(candidate),
        }

        if score > best_score:
            best_score = score
            best_candidate = candidate

    winner_info = vote_summary[best_candidate]
    is_confirmed = (
        best_score >= min_confidence
        and winner_info["vote_count"] >= min_votes
        and winner_info["is_valid_format"]
    )

    formatted_plate = format_plate_display(best_candidate) if is_confirmed else None

    return {
        "plate_text": formatted_plate,
        "confidence": round(best_score, 4),
        "unconfirmed": not is_confirmed,
        "best_candidate_raw": best_candidate,
        "vote_count": winner_info["vote_count"],
        "total_readings": total_valid_readings,
        "vote_summary": vote_summary,
    }
