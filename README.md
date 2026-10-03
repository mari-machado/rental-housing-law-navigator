# Rental Housing Law Navigator
 
Type an address. See which rental housing rules apply to it today, with the source text, and what a pending or new law would change.
 
Built for the 7th Hack-Nation Global AI Hackathon, challenge 02 (RealPage).
**Not legal advice.**
 
- Live demo: TODO
- Demo, tech and team videos: TODO
## What it does
 
1. **Extracts** rules from state and local housing law into structured records. An LLM reads each document. A rule is kept only if its quoted span appears verbatim in the source.
2. **Resolves** an address to its jurisdiction stack (state, county, city).
3. **Applies** each rule's coverage conditions (year built, units, owner type) to the building. Missing facts give "unknown", not a guess.
4. **Explains** each result in plain language with a citation and retrieval date.
5. **Tracks change:** for a new or pending law, lists affected addresses and the before/after rule set as of any date.
## Architecture
 
```
corpus -> extract.py -> rules.json
addresses -> geocode.py -> jurisdictions.json
rules + jurisdictions -> apply.py -> lookups.json
rules + lookups -> changes.py -> changes.json
rules/lookups/changes -> web/ (static front end)
```
 
The LLM extracts and explains. Plain code decides coverage, so results are auditable and repeatable.
 
## Results
 
| Measure | Score |
|---|---|
| Extraction (dev key) | TODO |
| Address coverage | TODO |
| Citations | TODO |
| Change tests T1-T6 | TODO |
  
## Data and sources
 
Provided starter pack (law corpus, sample addresses, schema). Public sources: Census Geocoder, Census TIGER/Line, state and local parcel data. Retrieval dates are stored with each rule.
 
## Responsible AI
 
- Every "applies" answer has a source and a quoted span.
- Enacted and pending law are shown separately, with an "as of" date.
- "Unknown" when the data lacks a needed fact.
- Conflicts and low-confidence answers are flagged for human review.
- Audit log of sources and model outputs in `audit.jsonl`.
- The tool does not suggest ways to avoid or structure around a rule.
## Limitations
 
TODO
 
## Structure
 
```
src/        pipeline scripts
data/       starter pack (not committed if large)
outputs/    rules.json, lookups.json, changes.json
web/        static front end
```
 
## License
 
MIT. See LICENSE.
 
