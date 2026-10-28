# StoryScout React interface

Implementation reference: the owner's `design.zip` export and supplied HTML.

The frontend follows the export's #101418 charcoal canvas, #0b0f12 rail,
#1c2024 cards, #94d4c5 teal highlights, #e7c27d warm bookmark state, and Inter
typography. Fonts, SVG icons, and illustrations are bundled, so the interface
does not need a font CDN or image service. Structural surfaces use 5–9px radii,
with fully rounded metadata chips and media controls. Desktop navigation is
244–260px wide, with a 65px top bar and a centered discovery spine.

The initial view has a real composer, four working suggestions, and four real
demonstration catalog entries. Conversation results form separate book and
movie grids. On small screens the rail becomes an off-canvas navigation menu,
and the composer respects the bottom safe area. Preferences and item details
use native modal dialogs styled as drawers, supporting Escape, focus trapping,
backdrop dismissal, and return of keyboard focus. Visible focus rings and a
skip link support keyboard navigation; reduced motion is respected.

Original SVG artwork is illustrative, not an official cover or poster. It
changes by catalog genres/themes. The mockup's invented titles, ratings,
resonance percentages, accounts, membership tiers, and staff endorsements are
not presented as real data. Similarity values appear only in the NLP detail
section and are named as such.

Saved stories and up to 12 conversations are stored per browser in localStorage.
Each conversation keeps up to 20 visible turns. They are not server accounts,
not shared across devices, and clearing browser data removes them. Data is not
used to train a personalization model.
