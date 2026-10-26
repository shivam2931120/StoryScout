from .schemas import CatalogItem
from .title_matching import resolve_title

def resolve_reference(query: str, catalogs: dict[str, list[CatalogItem]]) -> tuple[CatalogItem | None, list[CatalogItem]]:
    items = catalogs["book"] + catalogs["movie"]
    return resolve_title(query, items)

def reference_context(item: CatalogItem) -> str:
    return f"{item.title}. {item.description}. Genres: {', '.join(item.genres)}. Themes: {', '.join(item.theme_tags)}. Mood: {', '.join(item.mood_tags)}."
