"""Curated technical skill dictionary and taxonomy definitions.

Designed to be maintainable, extensible, and ready for future ESCO/O*NET ontology integration.
Employs precise regular expressions to prevent false-positive token collisions (e.g. C vs C++, Java vs JavaScript).
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SkillDefinition:
    """Definition of a canonical skill entity with taxonomy categorization and matcher regex."""

    canonical_name: str
    category: str
    aliases: List[str]
    pattern: re.Pattern


def _compile_skill_pattern(name: str, aliases: List[str], custom_regex: Optional[str] = None) -> re.Pattern:
    """Compile case-insensitive regex pattern with strict word boundary enforcement."""
    if custom_regex:
        return re.compile(custom_regex, re.IGNORECASE)

    # Standard token boundary pattern for multi-word or single-word skills
    escaped_variants = [re.escape(v) for v in [name] + aliases]
    pattern_str = r"\b(?:" + "|".join(escaped_variants) + r")\b"
    return re.compile(pattern_str, re.IGNORECASE)


# ---------------------------------------------------------------------------
# Curated Skill Taxonomy Definitions
# ---------------------------------------------------------------------------

SKILL_DEFINITIONS: List[SkillDefinition] = [
    # --- Programming Languages ---
    SkillDefinition(
        canonical_name="Python",
        category="Programming Languages",
        aliases=["python3", "python 3"],
        pattern=_compile_skill_pattern("Python", ["python3", "python 3"]),
    ),
    SkillDefinition(
        canonical_name="Java",
        category="Programming Languages",
        aliases=["Java8", "Java11", "Java17", "Java 8", "Java 11", "Java 17"],
        # Disallow matching Java when directly followed by Script (JavaScript)
        pattern=re.compile(r"\bJava(?!\s*Script\b)(?:\s*(?:8|11|17|21))?\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="JavaScript",
        category="Programming Languages",
        aliases=["JS", "Javascript", "ECMAScript"],
        pattern=re.compile(r"\b(?:JavaScript|Javascript|ECMAScript|\bJS\b)", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="TypeScript",
        category="Programming Languages",
        aliases=["TS", "Typescript"],
        pattern=re.compile(r"\b(?:TypeScript|Typescript|\bTS\b)", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="C",
        category="Programming Languages",
        aliases=[],
        # Strictly match standalone C; disallow C++ or C#; single-char fixed-width lookbehind
        pattern=re.compile(
            r"(?<![A-Za-z0-9_#+])\bC\b(?![A-Za-z0-9_#+])",
            re.IGNORECASE,
        ),
    ),
    SkillDefinition(
        canonical_name="C++",
        category="Programming Languages",
        aliases=["Cpp", "C plus plus"],
        pattern=re.compile(
            r"(?<![A-Za-z0-9_])(?:C\+\+(?![A-Za-z0-9_+])|\bCpp\b|\bC\s*plus\s*plus\b)",
            re.IGNORECASE,
        ),
    ),
    SkillDefinition(
        canonical_name="C#",
        category="Programming Languages",
        aliases=["CSharp", "C sharp"],
        pattern=re.compile(
            r"(?<![A-Za-z0-9_])(?:C#(?![A-Za-z0-9_#])|\bCSharp\b|\bC\s*sharp\b)",
            re.IGNORECASE,
        ),
    ),
    SkillDefinition(
        canonical_name="Go",
        category="Programming Languages",
        aliases=["Golang"],
        # Match Golang or Go when followed by lang/programming or as standalone token not followed by common prepositions
        pattern=re.compile(
            r"\b(?:Golang|Go(?:\s+(?:language|programming|lang))|\bGo\b(?!\s+(?:to|on|for|back|ahead|in|into|through|live|away|out)))\b",
            re.IGNORECASE,
        ),
    ),
    SkillDefinition(
        canonical_name="PHP",
        category="Programming Languages",
        aliases=["PHP7", "PHP8"],
        pattern=_compile_skill_pattern("PHP", ["PHP7", "PHP8"]),
    ),
    SkillDefinition(
        canonical_name="SQL",
        category="Programming Languages",
        aliases=["Structured Query Language"],
        pattern=_compile_skill_pattern("SQL", ["Structured Query Language"]),
    ),

    # --- Frontend ---
    SkillDefinition(
        canonical_name="HTML",
        category="Frontend",
        aliases=["HTML5"],
        pattern=re.compile(r"\bHTML[5]?\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="CSS",
        category="Frontend",
        aliases=["CSS3"],
        pattern=re.compile(r"\bCSS[3]?\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="React",
        category="Frontend",
        aliases=["React.js", "ReactJS", "React Native"],
        pattern=re.compile(r"\b(?:React(?:\.?js)?|ReactJS|React\s+Native)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Angular",
        category="Frontend",
        aliases=["AngularJS", "Angular.js"],
        pattern=re.compile(r"\b(?:Angular(?:\.?js)?|AngularJS)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Vue",
        category="Frontend",
        aliases=["Vue.js", "VueJS"],
        pattern=re.compile(r"\b(?:Vue(?:\.?js)?|VueJS)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Next.js",
        category="Frontend",
        aliases=["NextJS", "Nextjs", "Next"],
        pattern=re.compile(r"\b(?:Next(?:\.?js)?|NextJS|Nextjs)\b", re.IGNORECASE),
    ),

    # --- Backend ---
    SkillDefinition(
        canonical_name="FastAPI",
        category="Backend",
        aliases=["Fast-API"],
        pattern=_compile_skill_pattern("FastAPI", ["Fast-API"]),
    ),
    SkillDefinition(
        canonical_name="Django",
        category="Backend",
        aliases=["Django REST framework", "DRF"],
        pattern=_compile_skill_pattern("Django", ["Django REST framework", "DRF"]),
    ),
    SkillDefinition(
        canonical_name="Flask",
        category="Backend",
        aliases=[],
        pattern=_compile_skill_pattern("Flask", []),
    ),
    SkillDefinition(
        canonical_name="Node.js",
        category="Backend",
        aliases=["NodeJS", "Node.JS", "Node"],
        pattern=re.compile(r"\b(?:Node(?:\.?js)?|NodeJS)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Express",
        category="Backend",
        aliases=["Express.js", "ExpressJS"],
        pattern=re.compile(r"\b(?:Express(?:\.?js)?|ExpressJS)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Spring Boot",
        category="Backend",
        aliases=["SpringBoot", "Spring Framework", "Spring"],
        pattern=re.compile(r"\b(?:Spring\s*Boot|SpringBoot|Spring\s+Framework)\b", re.IGNORECASE),
    ),

    # --- Databases ---
    SkillDefinition(
        canonical_name="PostgreSQL",
        category="Databases",
        aliases=["Postgres", "Postgresql"],
        pattern=re.compile(r"\b(?:PostgreSQL|Postgresql|Postgres)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="MySQL",
        category="Databases",
        aliases=[],
        pattern=_compile_skill_pattern("MySQL", []),
    ),
    SkillDefinition(
        canonical_name="SQLite",
        category="Databases",
        aliases=["SQLite3"],
        pattern=_compile_skill_pattern("SQLite", ["SQLite3"]),
    ),
    SkillDefinition(
        canonical_name="MongoDB",
        category="Databases",
        aliases=["Mongo"],
        pattern=re.compile(r"\b(?:MongoDB|Mongo)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Redis",
        category="Databases",
        aliases=[],
        pattern=_compile_skill_pattern("Redis", []),
    ),

    # --- Data & Machine Learning ---
    SkillDefinition(
        canonical_name="pandas",
        category="Data & ML",
        aliases=[],
        pattern=_compile_skill_pattern("pandas", []),
    ),
    SkillDefinition(
        canonical_name="NumPy",
        category="Data & ML",
        aliases=["Numpy"],
        pattern=_compile_skill_pattern("NumPy", ["Numpy"]),
    ),
    SkillDefinition(
        canonical_name="scikit-learn",
        category="Data & ML",
        aliases=["sklearn", "scikit learn"],
        pattern=re.compile(r"\b(?:scikit-learn|scikit\s+learn|sklearn)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="PyTorch",
        category="Data & ML",
        aliases=["Torch"],
        pattern=re.compile(r"\b(?:PyTorch|Torch)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="TensorFlow",
        category="Data & ML",
        aliases=["Tensorflow", "TF"],
        pattern=re.compile(r"\b(?:TensorFlow|Tensorflow)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="NLP",
        category="Data & ML",
        aliases=["Natural Language Processing"],
        pattern=re.compile(r"\b(?:Natural\s+Language\s+Processing|\bNLP\b)", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Machine Learning",
        category="Data & ML",
        aliases=["ML"],
        pattern=re.compile(r"\b(?:Machine\s+Learning|\bML\b(?=\s+(?:model|algorithm|pipeline|system|project)))\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Deep Learning",
        category="Data & ML",
        aliases=["DL"],
        pattern=re.compile(r"\b(?:Deep\s+Learning|\bDL\b(?=\s+(?:model|network|architecture)))\b", re.IGNORECASE),
    ),

    # --- Tools & Infrastructure ---
    SkillDefinition(
        canonical_name="Git",
        category="Tools & Infrastructure",
        aliases=[],
        pattern=re.compile(r"\bGit(?!\s*Hub)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="GitHub",
        category="Tools & Infrastructure",
        aliases=["GitLab"],
        pattern=re.compile(r"\b(?:GitHub|GitLab)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Docker",
        category="Tools & Infrastructure",
        aliases=["Docker Compose"],
        pattern=_compile_skill_pattern("Docker", ["Docker Compose"]),
    ),
    SkillDefinition(
        canonical_name="Kubernetes",
        category="Tools & Infrastructure",
        aliases=["K8s", "K8S"],
        pattern=re.compile(r"\b(?:Kubernetes|K8s)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Linux",
        category="Tools & Infrastructure",
        aliases=["Ubuntu", "Debian", "CentOS", "RedHat"],
        pattern=_compile_skill_pattern("Linux", ["Ubuntu", "Debian", "CentOS", "RedHat"]),
    ),
    SkillDefinition(
        canonical_name="AWS",
        category="Tools & Infrastructure",
        aliases=["Amazon Web Services", "EC2", "S3"],
        pattern=re.compile(r"\b(?:AWS|Amazon\s+Web\s+Services)\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="Azure",
        category="Tools & Infrastructure",
        aliases=["Microsoft Azure"],
        pattern=_compile_skill_pattern("Azure", ["Microsoft Azure"]),
    ),

    # --- Testing & APIs ---
    SkillDefinition(
        canonical_name="pytest",
        category="Testing & APIs",
        aliases=["py.test"],
        pattern=_compile_skill_pattern("pytest", ["py.test"]),
    ),
    SkillDefinition(
        canonical_name="REST API",
        category="Testing & APIs",
        aliases=["RESTful API", "RESTful", "REST APIs"],
        pattern=re.compile(r"\b(?:REST\s*APIs?|RESTful(?:\s*APIs?)?|\bREST\b(?=\s+services?))\b", re.IGNORECASE),
    ),
    SkillDefinition(
        canonical_name="GraphQL",
        category="Testing & APIs",
        aliases=[],
        pattern=_compile_skill_pattern("GraphQL", []),
    ),
    SkillDefinition(
        canonical_name="Postman",
        category="Testing & APIs",
        aliases=[],
        pattern=_compile_skill_pattern("Postman", []),
    ),
]
