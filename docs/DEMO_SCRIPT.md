# Five-minute demonstration

Open http://127.0.0.1:8000 after starting FastAPI with the built React frontend.
The NLP page shows the actual active retrieval mode. No key is required.

1. Start with “Suggest a short mystery book with an unexpected ending.” Show book grouping, page metadata, and the explanation.
2. Say “No horror or graphic violence” and then “Only show books now”; show persistent exclusions and media switching.
3. Reset and ask “Recommend an uplifting movie under two hours.” Point out the separate runtime filter.
4. Ask “I enjoyed Interstellar. Recommend a book with similar themes.” Explain reference-medium versus desired-medium and the non-adaptation disclaimer.
5. Ask “I liked The Hobbit. Suggest a movie with a similar adventure feel.” Then ask “Why did you recommend this?” and “Show active preferences.”

During a result, open View details to show the source, explanation, and real
similarity components. Use the cross-media button to select that exact reference
ID. Save a story, open Saved stories, and reload to demonstrate browser storage.
Finish on Evaluation: explain the 44-query benchmark, incomplete developer
judgments, separate component metrics, and executed movie genre experiment.
