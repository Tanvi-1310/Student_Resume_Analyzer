"""Technical skill extraction engine.

Matches explicit technical skills against the curated taxonomy using regex patterns
with strict token boundary and negative lookahead guards.
Avoids substring collisions, normalizes aliases, selects high-value evidence snippets,
and guarantees 1:1 consistency between skill lists and category groupings.
"""

from typing import Dict, List, Optional, Set, Tuple

from app.schemas.parser import SkillEvidence
from app.services.skill_dictionary import SKILL_DEFINITIONS


def _extract_evidence_snippet(text: str, start_pos: int, end_pos: int, max_len: int = 120) -> str:
    """Extract the containing line or sentence around a matched token for evidence."""
    line_start = text.rfind("\n", 0, start_pos)
    line_start = 0 if line_start == -1 else line_start + 1

    line_end = text.find("\n", end_pos)
    line_end = len(text) if line_end == -1 else line_end

    line = text[line_start:line_end].strip()

    if len(line) <= max_len:
        return line

    left = max(0, start_pos - 40)
    right = min(len(text), end_pos + 40)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(text) else ""
    return f"{prefix}{text[left:right].strip()}{suffix}"


def _is_valid_c_occurrence(text: str, start: int) -> bool:
    """Verify that standalone C is not preceded by contextual qualifiers like Grade or Section."""
    preceding = text[max(0, start - 25) : start].strip()
    words = preceding.split()
    if words:
        last_word = words[-1].lower().rstrip(":#-")
        if last_word in {
            "grade",
            "section",
            "part",
            "category",
            "vitamin",
            "annex",
            "level",
            "tier",
            "schedule",
        }:
            return False
    return True


def _score_snippet_informativeness(snippet: str) -> int:
    """Score evidence snippet to prioritize descriptive bullet points over simple comma lists."""
    words = snippet.split()
    score = len(words)
    # Reward bullet points or descriptive experience lines
    if any(snippet.startswith(b) for b in ("•", "-", "*", "▪", "►")):
        score += 15
    # Penalize purely comma-separated enumeration lines
    if snippet.count(",") >= 3 and score < 15:
        score -= 5
    return score


def extract_skills(text: str) -> Tuple[List[SkillEvidence], Dict[str, List[str]]]:
    """Scan text for explicit occurrences of skills from the curated taxonomy.

    Returns:
        Tuple of (list_of_SkillEvidence, dict_of_skills_grouped_by_category).
        Guarantees strict 1:1 consistency between both fields.
    """
    extracted_skills: List[SkillEvidence] = []
    seen_canonical: Set[str] = set()

    for skill_def in SKILL_DEFINITIONS:
        canonical = skill_def.canonical_name
        if canonical in seen_canonical:
            continue

        best_alias: Optional[str] = None
        best_snippet: Optional[str] = None
        best_score = -999

        for match in skill_def.pattern.finditer(text):
            # Contextual guard for single-character language 'C'
            if canonical == "C" and not _is_valid_c_occurrence(text, match.start()):
                continue

            alias = match.group(0)
            snippet = _extract_evidence_snippet(text, match.start(), match.end())
            score = _score_snippet_informativeness(snippet)

            if best_alias is None or score > best_score:
                best_alias = alias
                best_snippet = snippet
                best_score = score

        if best_alias and best_snippet:
            seen_canonical.add(canonical)
            evidence = SkillEvidence(
                name=canonical,
                category=skill_def.category,
                matched_alias=best_alias,
                evidence_snippet=best_snippet,
            )
            extracted_skills.append(evidence)

    # Strictly derive skills_by_category from extracted_skills to guarantee 1:1 consistency
    skills_by_category: Dict[str, List[str]] = {}
    for skill in extracted_skills:
        skills_by_category.setdefault(skill.category, []).append(skill.name)

    return extracted_skills, skills_by_category
