"""Resume-only presentation catalog. Existing database template keys remain valid."""

THEMES = {
    "minimal": {"name": "Executive Minimal", "layout": "centered", "accent": "#181818", "font": "serif", "ats_safe": True, "description": "Centered masthead, monochrome rules and spacious, understated sections."},
    "modern": {"name": "Modern Professional", "layout": "banded", "accent": "#173c32", "font": "sans", "ats_safe": True, "description": "Split masthead, tinted section bands and a strong business hierarchy."},
    "ats_readable": {"name": "Technical ATS", "layout": "plain", "accent": "#202830", "font": "sans", "ats_safe": True, "description": "Linear, single-column reading order with standard headings and no decorative columns."},
    "professional": {"name": "Elegant Editorial", "layout": "editorial", "accent": "#3c3945", "font": "serif", "ats_safe": True, "description": "Serif masthead and hanging section labels in a generous editorial gutter."},
    "developer": {"name": "Contemporary Sidebar", "layout": "sidebar", "accent": "#1e3a5f", "font": "sans", "ats_safe": False, "description": "A quiet skills/education rail alongside a wider experience and project column."},
    "creative": {"name": "Creative Modern", "layout": "balanced", "accent": "#75433d", "font": "sans", "ats_safe": False, "description": "Full-width ribbon masthead and balanced independent content columns."},
    "student": {"name": "Student Classic", "layout": "banded", "accent": "#315b43", "font": "sans", "ats_safe": True, "description": "The existing education-friendly option, retained for saved resumes."},
}


def theme_for(key: str) -> dict:
    return THEMES.get(key, THEMES["ats_readable"])


def recommended_theme(role: str) -> str:
    role = role.lower()
    if any(word in role for word in ("engineer", "developer", "data", "security", "scientist", "technical")):
        return "ats_readable"
    if any(word in role for word in ("director", "executive", "chief", "vice president")):
        return "minimal"
    if any(word in role for word in ("editor", "writer", "research", "legal")):
        return "professional"
    if any(word in role for word in ("designer", "creative", "artist")):
        return "creative"
    return "modern"
