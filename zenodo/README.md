# Zenodo deposition inputs

`deposit-dataset.json` is the metadata for the archival record of the data layer, in the
shape Zenodo's deposit API expects. Nothing here has been deposited yet.

**How it is meant to be used, in this order**

1. Create a token on **`sandbox.zenodo.org`** first (Settings → API tokens) and run the
   deposit there. A published record can be edited but never deleted, so the draft is
   tested where a mistake is free.
2. `export ZENODO_TOKEN=…` and create a draft deposition, attaching the files, then check
   the metadata against what the sandbox renders. The endpoints are Zenodo's documented
   deposit API (`/api/deposit/depositions`); this file records the payload, not a claim
   that a command was run against it — nothing has been deposited as of 2026-09-10.
3. Fill every key under `_fill_in_before_deposit` and delete that key before submitting.
4. Deposit on the production site, record the DOI in `CITATION.cff`, the dataset card and `README.md` of the source repository
   and the dataset card, and re-run the document gates.

**Verified input, not assumed:** the licence identifier `cc-by-4.0` was confirmed against
Zenodo's own licence API on 2026-09-10 (title "Creative Commons Attribution 4.0
International"). The software route — a version DOI per GitHub release, a concept DOI
across releases — is blocked on a tag, and a tag needs today's uncommitted work committed.
