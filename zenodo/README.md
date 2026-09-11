# Zenodo deposition inputs

> **Pre-release, last revised 2026-09-11** (methodology v0.1). Definitions, wording and figures
> may still change; cite a snapshot — a release tag or a commit, not a branch — so that a later
> revision cannot move what your citation points at. Every figure quoted in this document set is
> asserted against the shipped evidence by `scripts/analyze.py`, which fails when a number and the
> evidence disagree and warns when a file is edited after the date above.

`deposit-dataset.json` is the metadata for the archival record of the **data layer**; `.zenodo.json` at
the repository root is what Zenodo's GitHub integration reads when it turns a **release** into a software
record. Nothing **published** as of 2026-09-11. A **draft record exists on the production site** — `22699009`,
35 files, 720,133 bytes, metadata attached, edit page <https://zenodo.org/deposit/22699009> — and it
stays a draft until someone clicks publish, which is the point: a draft can be discarded, a published
record can never be deleted.

**Release procedure, in the order that keeps the copies identical.** The data layer exists in three
places that are written by three different commands, so the order matters:

1. Edit, then run the gates (`scripts/analyze.py`, `scripts/verify_dataset_card.py`,
   `python3 tools/verify_docs.py`). Run them **before** tagging, not after — `scripts/analyze.py`
   rewrites `analysis/summary_tables.md`, whose last line carries a generation timestamp, so a
   re-run after a sync produces one byte-level difference that the checker reports as drift.
2. Commit, push, tag.
3. Rebuild the published copies **from the tag**: upload the data-layer payload to the dataset
   repository, and synchronise the Zenodo draft key by key.
4. Measure, do not assert: `python3 scripts/check_release_sync.py --ref <tag> --zenodo-draft <id>`
   (or `--zenodo <record id>` once published). Exit 0 means every file's hash agrees in all three
   places.
5. Publish. This is the only irreversible step, and it is deliberately a separate act.

Performed in this order on 2026-09-11: tag `v0.3.0-pre` at commit `8f96c47`, then both published
copies brought to it — the checker reports no findings. Correcting an overstated reproducibility
claim the same morning produced `v0.3.0-pre.2` at commit `c711118`, which **supersedes** the first
tag rather than moving it: a pushed tag is left where it is, because rewriting a reference someone
else may have fetched costs more than an extra tag. Both published copies and this draft now sit at
`v0.3.0-pre.2` — **36 files, 744,463 bytes, no findings against the tag, served text clean** — and
the GitHub release `v0.3.0-pre.2` exists as a **draft**, because a draft release is not archived and
Zenodo's GitHub integration has to be enabled on the author's account before the release is published.

**Authorship, decided 2026-09-11.** The creator is `2makeitwork` with an **empty affiliation**, and the
record's `notes` field says so in words: the author is an independent, unaffiliated individual, and no
institution is to be added to any byline, citation, dataset card or archive record on this project's
behalf. Zenodo
stores the empty string as `null`; that is the intended state, not an unfilled field. `publication_date`
is `2026-09-11` and `zenodo/deposit.sh` re-stamps it to the day of the run when `--publish` is passed, so
a draft revised today and published next week does not archive today's date.

**The two routes, and what each still needs**

| Route | Record | Needs | Licence field |
|---|---|---|---|
| Manual deposit of the evidence | dataset, `deposit-dataset.json` | done: a token was supplied on 2026-09-11 (not stored in any file) and the draft exists; publishing is the remaining step | `cc-by-4.0` — verified against Zenodo's licence API, title "Creative Commons Attribution 4.0 International" |
| GitHub integration | software, from a release | the repository enabled in Zenodo's GitHub settings **and a published GitHub release**: the tag `v0.3.0-pre` exists at commit `8f96c47` and `.zenodo.json` is committed at that tag, so only the release page and the integration toggle are missing — a draft release is not archived, and the release name becomes the record's version | `mit` — verified against the same API, title "MIT License", SPDX scheme, marked OSI-approved; note the archive also contains CC-BY-4.0 text and data, which one field cannot express |

**How it is meant to be used, in this order**

1. Create a token on **`sandbox.zenodo.org`** first (Settings → API tokens) and run the
   deposit there. A published record can be edited but never deleted, so the draft is
   tested where a mistake is free.
   *Deviation, recorded 2026-09-11:* the sandbox run was skipped and the draft was created directly on
   the production site. The reason this was acceptable rather than careless: a **draft** is discammable
   there too — only publishing is irreversible, and publishing needs a separate explicit flag (`--publish`,
   which additionally requires the `deposit:actions` token scope). What the sandbox would have caught,
   and did catch after the fact, is the endpoint mismatch described in step 2.
2. `export ZENODO_TOKEN=…` then `python3 zenodo/sync_draft.py --record <id> --ref <tag> --metadata`
   to bring an existing draft to a tag, or `./zenodo/deposit.sh` to create one. Files are staged by
   `scripts/build_data_layer.py`, which owns the payload manifest — the same list
   `scripts/check_release_sync.py` compares, so staging, checking and publishing cannot disagree.
   Neither command publishes anything unless `--publish` is passed to `deposit.sh`.
   *Endpoints, verified against record 22699009:* the documented legacy route
   `/api/deposit/depositions/{id}/files` answers `400` on the current site and `files-archive` answers
   `405`; what works is `/api/records/{id}/draft/files` — init with a **list** of `{"key": …}` objects,
   PUT the bytes to each entry's `links.content`, then POST each `links.commit`, and DELETE a key
   before re-adding it when its content changed.
3. Fill every key under `_fill_in_before_deposit` and delete that key before submitting.
   One of its former entries ("`creators[].affiliation` if you want one") was removed on 2026-09-11:
   the answer is that no affiliation is wanted, by decision.
4. **Commit and push before depositing a version meant to match the repositories.** The payload is
   assembled from the working tree, not from a commit, so an uncommitted edit lands in the archive one
   revision ahead of GitHub and Hugging Face. Observed on 2026-09-11: the draft's `methodology.md` is
   9,311 bytes (with the pre-release notice) while the copy the two repositories served at that moment
   was the 8,844-byte revision of 2026-09-10. Citing a Zenodo snapshot and a repository branch together
   can therefore mix revisions — cite the snapshot for both.
5. Deposit on the production site, record the DOI in `CITATION.cff`, the dataset card and `README.md` of the source repository
   and the dataset card, and re-run the document gates.

**Verified input, not assumed:** both licence identifiers were read from Zenodo's own licence API rather
than guessed — `cc-by-4.0` and `mit`. A version DOI is minted per GitHub release and a concept DOI spans
releases, so the software route is blocked on a tag, and a tag needs today's uncommitted work committed.
