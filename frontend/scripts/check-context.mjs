import assert from 'node:assert/strict';
import { removeTopicTerm, preferenceChips, emptyState } from '../src/api.js';
assert.equal(removeTopicTerm('space exploration', 'space'), 'exploration');
assert.equal(removeTopicTerm('spacecraft space exploration', 'space'), 'spacecraft exploration');
assert.equal(removeTopicTerm('time travel and identity', 'time travel'), 'and identity');
const state=emptyState();
state.preferences.referenced_title='Interstellar';
assert.equal(preferenceChips(state).find(chip=>chip.field==='reference').text,'Like Interstellar');
console.log('4 frontend context checks passed');
