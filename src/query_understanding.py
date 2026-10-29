"""Local query reconstruction and descriptive semantic prototypes.

These transparent prototypes are not a trained sentiment model. Extracted
keywords and inferred tones/themes remain distinct from factual catalog tags.
"""
import re
from .schemas import Preferences
from .preprocessing import normalize_text

MOOD_PROTOTYPES = {
    'uplifting':'An optimistic, uplifting story of hope, courage, friendship and positive change that ends on a hopeful note.',
    'cheerful':'A cheerful happy light comedy, joyful humorous situations and good natured fun.',
    'comforting':'A comforting warm gentle story about kindness, supportive friends, home and belonging.',
    'cozy':'A cozy gentle story of quiet everyday life, community, friendship and a safe welcoming home.',
    'hopeful':'A hopeful story about resilience, overcoming difficulties, second chances and rebuilding life.',
    'inspiring':'An inspiring story of determination, perseverance, achieving a dream and overcoming adversity.',
    'thoughtful':'A contemplative philosophical story about identity, memory, meaning, ethical questions and human relationships.',
    'dark':'A dark disturbing tragic story about fear, danger, cruelty, obsession, bleakness and loss.',
    'funny':'A funny comedy with jokes, absurd situations, misunderstandings and humorous adventures.',
    'calm':'A calm quiet peaceful story with gentle everyday moments, reflection, nature and personal relationships.',
    'exciting':'A tense exciting fast paced adventure with suspense, escapes, action and high stakes.',
    'lighthearted':'A lighthearted playful comic story with romance, humor and entertaining mishaps.',
    'melancholic':'A melancholic bittersweet story of grief, loneliness, nostalgia, separation and loss.',
}
THEME_PROTOTYPES = {
    'time travel':'Travel into the past or future, a time machine, changing history, paradoxes or a repeating time loop.',
    'space':'Space exploration, astronauts, distant planets, a spacecraft and the challenges of a mission beyond Earth.',
    'friendship':'Friends supporting each other through difficulties, loyalty and companionship.',
    'identity':'A search for personal identity, self discovery, memory and what it means to be human.',
    'coming of age':'A young person growing up, facing adult responsibilities and discovering independence.',
    'found family':'Unrelated people become a supportive chosen family and find belonging together.',
    'survival':'Surviving isolation, disaster or dangerous conditions using resourcefulness and determination.',
    'magic':'Magical powers, spells, wizards and supernatural fantasy worlds.',
    'journey':'A quest or long journey through unfamiliar places that changes the travelers.',
    'artificial intelligence':'Robots or artificial intelligence, autonomous machines, consciousness and machine ethics.',
    'adventure':'An adventurous quest, exploration, discovery, daring escapes and unfamiliar worlds.',
    'justice':'An investigation, crime, wrongdoing, justice and moral responsibility.',
    'heist':'Planning and executing a robbery, clever deception, criminals and an elaborate heist.',
    'family':'Relationships between parents, children, siblings and relatives, and family bonds.',
}

ADMIN_WORDS = {'but','about','across','published','released','classic','language','english','hindi','spanish','french','german','this','that','same','similar','themes','feeling','tone','actually','instead','recommend','recommendation','recommendations','suggest','suggestion','suggestions','find','show','give','please','something','anything','stories','story','book','books','novel','novels','movie','movies','film','films','watch','read','reading','watching','now','only','also','make','shorter','short','longer','duration','length','pages','page','minutes','minute','mins','hours','hour','under','below','maximum','minimum','limit','limits','preferences','preference','apply','discovery','criteria','results','picks','different','more','another','some','these','those','them','it','with','without','my','me','a','an','the','to','for','of','and','or','is','in','at','most','less','than','up','two','one','three','year','years','from','through','after','before','between'}


def meaningful_query(text: str) -> str:
    """Remove commands and numeric/filter clauses instead of searching UI prose."""
    # A user's present emotion describes the person, not the requested story.
    text = re.sub(r"\bi\s+(?:feel(?:ing)?|am feeling|'m feeling)\s+.*?(?=[.;!?]|\b(?:suggest|recommend|find|give|show)\b|$)", ' ', str(text),flags=re.I)
    text = re.sub(r"\bi(?: am|'m)\s+(?:sad|stressed|anxious|tired|lonely|depressed|happy)\b",' ',text,flags=re.I)
    text = re.sub(r"\b(?:less intense|not too intense)\b", " ", text, flags=re.I)
    text = normalize_text(text)
    text = re.sub(r'\b(?:no|not|without|exclude|excluding|avoid|anything but)\s+(?:[\w-]+(?:\s+(?:and|or)\s+[\w-]+)*)', ' ', text)
    text = re.sub(r'\b(?:under|over|after|before|between|from|until|up to|max|maximum)\s+[\d\s.]+(?:pages?|minutes?|mins?|hours?|and)?', ' ', text)
    return ' '.join(word for word in text.split() if not word.isdigit() and word not in ADMIN_WORDS)


def build_search_query(text: str, preferences: Preferences, previous: str = '', followup: bool = False) -> tuple[str,str]:
    content = meaningful_query(text)
    # A refinement does not replace the meaningful original topic with "shorter".
    topic = ' '.join(dict.fromkeys([previous, content])) if followup and previous else content
    from .preferences import GENRES, GENRE_ALIASES, MOODS
    # Form edits must not keep searching an old genre or mood from the last message.
    descriptors = list(GENRES)+list(MOODS)+[x for values in GENRE_ALIASES.values() for x in values]+['feel good','feel-good','happy','gentle','warm','cerebral','mind bending','mind-bending']
    for term in sorted(descriptors,key=len,reverse=True):
        topic=re.sub(rf'\b{re.escape(term)}\b',' ',topic,flags=re.I)
    topic=re.sub(r'\bi (?:enjoyed|liked|loved)\b',' ',topic,flags=re.I)
    for term in preferences.negative_content:
        for word in term.split(): topic=re.sub(rf'\b{re.escape(word)}\b',' ',topic,flags=re.I)
    topic=' '.join(topic.split())
    pieces = [topic]
    pieces.extend(preferences.preferred_genres)
    pieces.extend(THEME_PROTOTYPES.get(theme,theme) for theme in preferences.themes)
    if preferences.desired_mood:
        pieces.append(MOOD_PROTOTYPES.get(preferences.desired_mood, preferences.desired_mood))
    return ' '.join(dict.fromkeys(piece for piece in pieces if piece)).strip(), topic


def content_chunks(text: str, words_per_chunk: int = 140, maximum: int = 3) -> list[str]:
    words = text.split()
    if len(words) <= words_per_chunk: return [text]
    starts = sorted(set([0, max(0,(len(words)-words_per_chunk)//2), max(0,len(words)-words_per_chunk)]))
    return [' '.join(words[start:start+words_per_chunk]) for start in starts[:maximum]]
