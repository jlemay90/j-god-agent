"""Conservative, opt-in identity masking. NOT a complete PII anonymizer.

Supply known names/attributes for reliable exact-span replacement. Heuristics
catch titled names, age expressions and selected affiliations; they miss context,
unknown names and indirect identity clues. Keep restoration maps local/private.
"""
import json
import re
from dataclasses import dataclass


@dataclass
class MaskedText:
    text: str
    restoration_map: dict[str, str]

    def to_json(self) -> str:
        return json.dumps({'text': self.text, 'restoration_map': self.restoration_map},
                          ensure_ascii=False)


def mask(text: str, known_entities: dict[str, str] | None = None) -> MaskedText:
    if re.search(r'\[(?:PERSON|AGE|TITLE|ETHNICITY|RELIGION)_\d+\]', text):
        raise ValueError('Input already contains reserved identity tokens')
    spans = []
    # Explicit entities take precedence over heuristics; values are token classes.
    allowed = {'PERSON', 'AGE', 'TITLE', 'ETHNICITY', 'RELIGION'}
    for value, category in (known_entities or {}).items():
        if not value or category not in allowed:
            raise ValueError('Provide nonempty entities and a supported token class')
        for m in re.finditer(r'(?<!\w)' + re.escape(value) + r'(?!\w)', text, re.I):
            spans.append((m.start(), m.end(), category, 0))
    patterns = {
        'PERSON': r'\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Professor)\s+[A-Z][a-z]+(?:[ -][A-Z][a-z]+){1,3}\b',
        'AGE': r'\b(?:aged?\s+\d{1,3}|\d{1,3}[ -]years?[ -]old)\b',
        'TITLE': r'\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Professor)(?=\s)',
        'ETHNICITY': r'\b(?:African American|Asian American|Hispanic|Latino|Latina|Caucasian)\b',
        'RELIGION': r'\b(?:Christian|Muslim|Jewish|Hindu|Buddhist|Sikh|atheist)\b',
    }
    for category, pattern in patterns.items():
        for m in re.finditer(pattern, text, 0 if category == 'PERSON' else re.I):
            spans.append((m.start(), m.end(), category, 1))
    chosen = []
    for span in sorted(spans, key=lambda s: (s[3], -(s[1]-s[0]), s[0])):
        if not any(span[0] < end and span[1] > start for start, end, *_ in chosen):
            chosen.append(span)
    restoration = {}
    lookup = {}
    counts = {}
    parts, cursor = [], 0
    for start, end, category, _ in sorted(chosen):
        original = text[start:end]
        key = (category, original)  # preserve exact spelling on restoration
        if key not in lookup:
            counts[category] = counts.get(category, 0) + 1
            lookup[key] = f'[{category}_{counts[category]}]'
            restoration[lookup[key]] = original
        parts.extend((text[cursor:start], lookup[key]))
        cursor = end
    parts.append(text[cursor:])
    return MaskedText(''.join(parts), restoration)


def restore(text: str, restoration_map: dict[str, str]) -> str:
    # Single pass: restored source text cannot trigger recursive replacement.
    return re.sub(r'\[(?:PERSON|AGE|TITLE|ETHNICITY|RELIGION)_\d+\]',
                  lambda m: restoration_map.get(m.group(), m.group()), text)
