from __future__ import annotations
from .schemas import CatalogItem, Preferences, Recommendation

def explain(rec: Recommendation, query: str, pref: Preferences) -> str:
    item = rec.item
    bits = []
    matched = sorted(set(item.genres) & set(pref.preferred_genres))
    if matched: bits.append("matches " + ", ".join(matched))
    subject_matches=sorted(set(item.subject_genres)&set(pref.preferred_genres))
    if subject_matches: bits.append('has source subject headings mapped to '+', '.join(subject_matches))
    if pref.desired_mood and pref.desired_mood in item.mood_tags: bits.append(f"has the catalog mood tag '{pref.desired_mood}'")
    themes = sorted(set(item.theme_tags) & set(pref.themes))
    if themes: bits.append("supports the theme(s) " + ", ".join(themes))
    if pref.desired_mood and pref.desired_mood not in item.mood_tags and rec.score_components.get('mood_alignment',0) >= .35:
        bits.append(f"has text aligned with a {pref.desired_mood} tone (NLP inference)")
    if rec.matched_terms: bits.append('shares text signals: ' + ', '.join(rec.matched_terms[:3]))
    if pref.language and pref.language.lower() in item.language.lower().split('|'): bits.append(f"lists {pref.language} in its source language metadata")
    if item.year and ((pref.min_year and item.year >= pref.min_year) or (pref.max_year and item.year <= pref.max_year)): bits.append(f"fits the year range ({item.year})")
    if item.page_count and pref.max_pages: bits.append(f"is {item.page_count} pages, within the limit")
    if item.runtime_minutes and pref.max_runtime: bits.append(f"runs {item.runtime_minutes} minutes, within the limit")
    if 'filter-only results; no text similarity signal' in rec.filter_notes or rec.score <= 0:
        bits.append("satisfies the active filters; no matching text terms were found in the catalog")
    elif not bits:
        bits.append("has the strongest available text similarity to your request")
    suffix = " Content-safety metadata is incomplete, so unknown warnings were not treated as verified absence." if pref.negative_content and not item.verified_warnings else ""
    return "Recommended because it " + "; ".join(bits) + "." + suffix

def explain_reference(rec: Recommendation, reference: CatalogItem, pref: Preferences) -> str:
    base = explain(rec, f"similar to {reference.title}", pref)
    return base + f" This is a description/theme similarity to '{reference.title}', not a verified adaptation claim."
