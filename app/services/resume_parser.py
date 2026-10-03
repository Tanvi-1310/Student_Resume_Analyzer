"""Master structured resume parsing service.

Orchestrates section boundary detection, contact extraction, and technical skill matching.
Translates unstructured text into structured, testable domain schemas without fabricating data.
"""

from typing import List

from app.schemas.parser import StructuredResumeResponse
from app.services.contact_extractor import extract_contact_info
from app.services.section_detector import detect_sections
from app.services.skill_extractor import extract_skills

STANDARD_SECTIONS: List[str] = [
    "education",
    "experience",
    "skills",
    "projects",
]


class ResumeParserService:
    """Service coordinating end-to-end extraction of structured data from resume text."""

    def __init__(self, standard_sections: List[str] = STANDARD_SECTIONS) -> None:
        self.standard_sections = standard_sections

    def parse_resume_text(
        self,
        text: str,
        filename: str = "resume.pdf",
    ) -> StructuredResumeResponse:
        """Parse raw resume text into structured section, contact, and skill components.

        Args:
            text: Plain text extracted from resume document.
            filename: Associated document name for tracking.

        Returns:
            StructuredResumeResponse with all extracted entities and diagnostic warnings.
        """
        warnings: List[str] = []
        parser_notes: List[str] = []

        # 1. Section Boundary Detection
        detected_sections, sec_warnings = detect_sections(text)
        warnings.extend(sec_warnings)

        detected_section_keys = list(detected_sections.keys())
        missing_standard_sections = [
            s for s in self.standard_sections if s not in detected_sections
        ]

        if missing_standard_sections:
            missing_names = ", ".join(s.capitalize() for s in missing_standard_sections)
            warnings.append(
                f"Standard resume section(s) not identified: {missing_names}."
            )

        # 2. Contact Coordinates Extraction
        contact_info = extract_contact_info(text)
        if not contact_info.email and not contact_info.phone:
            warnings.append(
                "Neither an email address nor a phone number could be reliably identified."
            )

        # 3. Technical Skill Extraction
        skills, skills_by_category = extract_skills(text)
        if not skills:
            warnings.append(
                "No canonical technical skills from the standard taxonomy were detected."
            )
        else:
            parser_notes.append(
                f"Identified {len(skills)} canonical technical skills across "
                f"{len(skills_by_category)} categories."
            )

        parser_notes.append(
            f"Detected {len(detected_sections)} sections ({', '.join(detected_section_keys) if detected_section_keys else 'none'})."
        )

        return StructuredResumeResponse(
            filename=filename,
            contact_info=contact_info,
            detected_sections=detected_sections,
            detected_section_keys=detected_section_keys,
            missing_standard_sections=missing_standard_sections,
            skills=skills,
            skills_by_category=skills_by_category,
            warnings=warnings,
            parser_notes=parser_notes,
        )


# Singleton service instance
resume_parser_service = ResumeParserService()
