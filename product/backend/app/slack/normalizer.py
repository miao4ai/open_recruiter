"""Stage 2: Normalize parsed resume fields into consistent format."""

from __future__ import annotations

import re

# Canonical skill names — maps lowercase variant to preferred form.
_SKILL_CANONICAL: dict[str, str] = {
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "python": "Python",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C#",
    "csharp": "C#",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "ruby": "Ruby",
    "php": "PHP",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "sql": "SQL",
    "nosql": "NoSQL",
    "mongodb": "MongoDB",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "redis": "Redis",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "terraform": "Terraform",
    "graphql": "GraphQL",
    "rest": "REST",
    "html": "HTML",
    "css": "CSS",
    "sass": "Sass",
    "scss": "Sass",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "pandas": "pandas",
    "numpy": "NumPy",
    "git": "Git",
    "linux": "Linux",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "AI",
    "llm": "LLM",
    "nlp": "NLP",
}


def normalize_profile(parsed: dict) -> dict:
    """Standardize profile fields for consistency."""
    result = parsed.copy()

    result["name"] = _title_case(result.get("name", ""))
    result["current_title"] = _title_case(result.get("current_title", ""))
    result["current_company"] = _title_case(result.get("current_company", ""))
    result["location"] = _title_case(result.get("location", ""))
    result["email"] = result.get("email", "").strip().lower()
    result["phone"] = _normalize_phone(result.get("phone", ""))
    result["skills"] = _normalize_skills(result.get("skills", []))

    return result


def _title_case(s: str) -> str:
    """Title-case a string, preserving already-capitalized abbreviations."""
    if not s or not s.strip():
        return ""
    return s.strip().title()


def _normalize_skills(skills: list[str]) -> list[str]:
    """Deduplicate and canonicalize skill names."""
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        skill = skill.strip()
        if not skill:
            continue
        canonical = _SKILL_CANONICAL.get(skill.lower(), skill)
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            result.append(canonical)
    return result


def _normalize_phone(phone: str) -> str:
    """Normalize phone to a consistent readable format."""
    if not phone:
        return ""
    # Strip everything except digits and leading +
    has_plus = phone.strip().startswith("+")
    digits = re.sub(r"[^\d]", "", phone)
    if not digits:
        return phone.strip()

    # US 10-digit number
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    # US 11-digit (leading 1)
    if len(digits) == 11 and digits[0] == "1":
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    # International: just group with the plus
    if has_plus:
        return f"+{digits}"
    return digits
