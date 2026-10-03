"""Resume section boundary detection and structured section parser.

Identifies canonical resume sections (Summary, Education, Experience, Projects,
Skills, Certifications, Achievements, Publications, Extracurriculars) using strict
line-level matching to prevent false positives within body prose.
"""

import re
from typing import Dict, List, Optional, Tuple

from app.schemas.parser import SectionContent

# ---------------------------------------------------------------------------
# Heading Pattern Specifications
# ---------------------------------------------------------------------------

SECTION_HEADINGS: Dict[str, List[str]] = {
    "summary": [
        r"professional\s+summary",
        r"career\s+summary",
        r"summary\s+of\s+qualifications",
        r"executive\s+summary",
        r"summary",
        r"career\s+objective",
        r"objective",
        r"professional\s+profile",
        r"profile",
        r"about\s+me",
    ],
    "education": [
        r"academic\s+background",
        r"academic\s+history",
        r"educational\s+qualifications",
        r"academic\s+qualifications",
        r"qualifications",
        r"education",
        r"academic\s+record",
    ],
    "experience": [
        r"work\s+experience",
        r"professional\s+experience",
        r"employment\s+history",
        r"work\s+history",
        r"internship\s+experience",
        r"internships",
        r"employment",
        r"experience",
    ],
    "projects": [
        r"academic\s+projects",
        r"personal\s+projects",
        r"technical\s+projects",
        r"key\s+projects",
        r"software\s+projects",
        r"projects",
    ],
    "skills": [
        r"technical\s+skills",
        r"core\s+competencies",
        r"core\s+skills",
        r"key\s+skills",
        r"programming\s+skills",
        r"technologies",
        r"skills\s+&\s+technologies",
        r"tools\s+&\s+technologies",
        r"skills",
    ],
    "certifications": [
        r"certifications\s+&\s+licenses",
        r"licenses\s+&\s+certifications",
        r"professional\s+certifications",
        r"courses\s+&\s+certifications",
        r"certifications",
        r"certificates",
        r"licenses",
        r"credentials",
    ],
    "achievements": [
        r"honors\s+&\s+awards",
        r"awards\s+&\s+achievements",
        r"accomplishments",
        r"key\s+achievements",
        r"achievements",
        r"awards",
        r"honors",
    ],
    "publications": [
        r"research\s+publications",
        r"conference\s+proceedings",
        r"publications",
    ],
    "extracurricular": [
        r"extracurricular\s+activities",
        r"extracurriculars",
        r"volunteer\s+experience",
        r"volunteering",
        r"community\s+involvement",
        r"leadership\s+&\s+activities",
        r"leadership",
        r"activities",
    ],
}

# Compile fullmatch patterns for each section key
COMPILED_SECTION_PATTERNS: Dict[str, List[re.Pattern]] = {
    section_key: [re.compile(rf"^{pat}$", re.IGNORECASE) for pat in patterns]
    for section_key, patterns in SECTION_HEADINGS.items()
}

# Conservative date pattern for extracting year/month mentions
DATE_PATTERN = re.compile(
    r"\b(?:"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[,\s]+(?:\d{4}|\d{2})"
    r"|\d{4}\s*[-–—]\s*(?:\d{4}|Present|Current)"
    r"|(?:19\d{2}|20\d{2})"
    r")\b",
    re.IGNORECASE,
)

# Standard bullet point markers
BULLET_PREFIX_PATTERN = re.compile(r"^[\s\t]*[•\-\*▪▫►–—\d+\.]\s*")


def _clean_candidate_heading(line: str) -> str:
    """Strip markdown formatting, colons, and surrounding punctuation/whitespace from a candidate line."""
    clean = re.sub(r"^#{1,6}\s*", "", line).strip()
    clean = re.sub(r"^[\s*_\-—]+|[\s*_\-—:]+$", "", clean).strip()
    return clean


def _match_section_heading(line: str) -> Optional[str]:
    """Test whether a line corresponds to an acknowledged section heading.

    Enforces bounds on word count and character length to disallow matching body sentences.
    """
    clean_line = _clean_candidate_heading(line)
    if not clean_line or len(clean_line) > 55 or len(clean_line.split()) > 6:
        return None

    for section_key, patterns in COMPILED_SECTION_PATTERNS.items():
        for pat in patterns:
            if pat.fullmatch(clean_line):
                return section_key

    return None


def extract_bullet_points(section_text: str) -> List[str]:
    """Extract bullet points or distinctive entries from section text."""
    bullets: List[str] = []
    lines = section_text.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check if line begins with a bullet marker
        if BULLET_PREFIX_PATTERN.match(line):
            cleaned = BULLET_PREFIX_PATTERN.sub("", line).strip()
            if cleaned:
                bullets.append(cleaned)
        elif len(stripped) > 5:
            # Include clean standalone line as an entry
            bullets.append(stripped)

    return bullets


def extract_dates(section_text: str) -> List[str]:
    """Extract chronological dates mentioned in a section using conservative regex."""
    found = DATE_PATTERN.findall(section_text)
    # Deduplicate preserving order
    seen = set()
    deduped = []
    for d in found:
        d_clean = d.strip()
        if d_clean and d_clean not in seen:
            seen.add(d_clean)
            deduped.append(d_clean)
    return deduped


def detect_sections(text: str) -> Tuple[Dict[str, SectionContent], List[str]]:
    """Scan resume text, identify section boundaries, and extract structured contents.

    Returns:
        A tuple of (detected_sections_dict, warnings_list).
    """
    lines = text.splitlines()
    detected_markers: List[Tuple[int, str, str]] = []  # (line_index, section_key, raw_heading)

    for idx, line in enumerate(lines):
        sec_key = _match_section_heading(line)
        if sec_key:
            detected_markers.append((idx, sec_key, line.strip()))

    detected_sections: Dict[str, SectionContent] = {}
    warnings: List[str] = []

    if not detected_markers:
        warnings.append(
            "No standard section headings were recognized in the document text. "
            "The resume may use unconventional layouts, narrative prose, or image headers."
        )
        return detected_sections, warnings

    # Segment text between sequential markers
    for i, (start_idx, sec_key, raw_heading) in enumerate(detected_markers):
        end_idx = detected_markers[i + 1][0] if i + 1 < len(detected_markers) else len(lines)
        section_lines = lines[start_idx + 1 : end_idx]
        raw_section_text = "\n".join(section_lines).strip()

        bullets = extract_bullet_points(raw_section_text)
        dates = extract_dates(raw_section_text)

        detected_sections[sec_key] = SectionContent(
            section_key=sec_key,
            heading=raw_heading,
            raw_text=raw_section_text,
            bullet_points=bullets,
            detected_dates=dates,
        )

    return detected_sections, warnings
