"""Transparent relevance gates and bounded preference boosts.

These are conservative engineering defaults, not learned probabilities or
independently optimized cutoffs. Keep this policy separate from model caches.
"""
import numpy as np

POLICIES = {
    'book': {'lexical_floor': .045, 'semantic_floor': .30, 'score_floor': .045, 'relative_floor': .50},
    'movie': {'lexical_floor': .035, 'semantic_floor': .32, 'score_floor': .055, 'relative_floor': .50},
}


def topic_gate(domain, lexical, semantic):
    policy = POLICIES[domain]
    matches = lexical >= policy['lexical_floor']
    if semantic is not None:
        matches |= semantic >= policy['semantic_floor']
    return matches


def preference_boost(base, genre, mood, theme, learned):
    # A zero topic match stays zero; preferences cannot manufacture relevance.
    return np.minimum(1., base * (1. + .12*genre + .08*mood + .10*theme + .04*learned))


def quality_gate(domain, base, topic_matches):
    policy = POLICIES[domain]
    best = float(np.max(base[topic_matches])) if np.any(topic_matches) else 0.
    cutoff = max(policy['score_floor'], best*policy['relative_floor'])
    return topic_matches & (base >= cutoff), cutoff
