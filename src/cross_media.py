from .schemas import CatalogItem
from .title_matching import resolve_title

def resolve_reference(query: str, catalogs: dict[str, list[CatalogItem]]) -> tuple[CatalogItem | None, list[CatalogItem]]:
    items = catalogs["book"] + catalogs["movie"]
    return resolve_title(query, items)

def reference_context(item: CatalogItem) -> str:
    metadata_only = item.source.startswith(("movielens", "project-gutenberg", "wikidata-catalog", "openlibrary-catalog")) and not item.description_provenance
    text=item.retrieval_text or ("" if metadata_only else item.description)
    return f"{item.title}. {text[:2200]}. Genres: {', '.join(item.genres)}. Themes: {', '.join(item.theme_tags)}. Mood: {', '.join(item.mood_tags)}."
