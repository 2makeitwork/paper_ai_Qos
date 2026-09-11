# Zenodo deposition inputs

> **Released 2026-09-11 as v1.0.1** (methodology v0.1). This snapshot is frozen: later
> corrections and additions ship as a new version with a new tag, never as an edit to the bytes a
> citation points at — cite the tag or the Digital Object Identifier, not a branch. Two version
> numbers mean two different things here: the tag names this public snapshot, while *methodology
> v0.1* names the definitions, which stay unchanged until a second provider has been measured
> (section 7). Every figure quoted in this document set is asserted against the shipped evidence by
> `scripts/analyze.py`, which fails when a number and the evidence disagree and warns when a file
> is edited after the date above.

`deposit-dataset.json` is the metadata for the archival record of the **data layer**; `.zenodo.json` at
the repository root is what Zenodo's GitHub integration reads when it turns a **release** into a software
record. Nothing **published** as of 2026-09-11. A **draft record exists on the production site** — `22699009`,
35 files, 720,133 bytes, metadata attached, edit page <https://zenodo.org/deposit/22699009> — and it
stays a draft until someone clicks publish, which is the point: a draft can be discarded, a published
record can never be deleted.

**Release procedure, in the order that keeps the copies identical.** The data layer exists in three
places that are written by three different commands, so the order matters:

1. Edit, then run the gates — `./scripts/preflight.sh` runs them in order and prints `READY` or
   `NOT READY TO PUBLISH`. A verification run cannot dirty the tree: `analyze.py`
   rewrites `analysis/summary_tables.md` only when the content hash in its last line changes, so
   re-running on the same statistics leaves that file, and its timestamp, exactly where they were.
2. Commit, push, tag.
3. Rebuild the published copies **from the tag**: upload the data-layer payload to the dataset
   repository, and synchronise the Zenodo draft key by key.
4. Measure, do not assert: `./scripts/preflight.sh --release <tag>`. That is the single entry
   point — it runs the assertions, the card check, the document gate, the tracked-set and identity
   checks, the payload staging, and then `scripts/check_release_sync.py` against the tag and (with
   `ZENODO_TOKEN` set) the draft record. Exit 0 means every file's hash agrees in all three places
   and nothing in the served text is addressed to the maintainer. Plain `./scripts/preflight.sh`
   runs the offline part anywhere.
5. Publish. This is the only irreversible step, and it is deliberately a separate act.
   The GitHub release note is authored in `RELEASE_NOTES.md` and applied with
   `gh release edit <tag> --notes-file RELEASE_NOTES.md`, so the text a stranger reads is a
   tracked file that `scripts/analyze.py` scans — not prose typed into a command line. The
   release itself stays a **draft** until Zenodo's GitHub integration is enabled on the
   author's account: a draft release is never archived, and a release published while the
   integration is off is not archived afterwards either.

*Deviation, recorded 2026-09-11 for the first formal release.* `v1.0.0` was published as a GitHub
release **before** the integration could be enabled, because the integration turned out to be
unusable that day (see the table below) and holding the public release for it would have delayed
the release itself. What that costs: no software record was created automatically for `v1.0.0`, and
enabling the integration afterwards will not retroactively archive it. What it does not cost:
nothing about the release is wrong or lost — the tag, the source archive and the dataset record all
stand — and a version identifier for the software can still be minted by a manual deposit, at the
price of not sharing a concept identifier with the releases the integration will handle later.
For subsequent releases the rule above holds without exception: enable, verify the hook exists,
then publish.

Performed on 2026-09-11, in this order: tag `v0.3.0-pre` at commit `8f96c47`, with both published
copies brought to it. Correcting an overstated reproducibility claim the same morning produced
`v0.3.0-pre.2` at `c711118`; making the gates test the published tree instead of this workstation
produced `v0.3.0-pre.3` at `b56c1b3`; naming the citable snapshot produced `v0.3.0-pre.4` at
`eef47c1`. The author then rewrote the positioning — the contribution as a novelty of perspective
rather than of method, with section 7.1 added — and that text was packaged and published as the
formal release **`v1.0.0` at commit `fd431d8`**, which is the tag to cite. Superseded tags are left
where they are rather than moved: rewriting a reference someone else may already have fetched costs
more than an extra tag. The superseded *draft releases* were deleted (their tags kept) so that
exactly one release exists and the wrong one cannot be published.

At `v1.0.0` the archive draft and the dataset repository are both byte-identical to the tag —
36 files, 757,653 bytes, zero findings against the tag and no internal instruction text in what is
served, measured 2026-09-11 by
`scripts/check_release_sync.py --ref v1.0.0 --zenodo-draft 22699009`, which reports `IN SYNC`.

**The tag was moved, once, by the author's explicit instruction.** `v1.0.0` first pointed at commit
`fd431d8`; two follow-up commits fixed published text (editorial routing notes in a heading of
`abstract.md`, a local-only tool inventory in `README.md`, the release-procedure section addressed
to the maintainer rather than to a reader) and the version was briefly bumped to `v1.0.1` to carry
them forward. The author directed instead that they fold into `v1.0.0` by amending and
force-pushing, so the citable snapshot is `ce31ea9` and the release was re-pointed at it
(`gh release edit v1.0.0 --notes-file RELEASE_NOTES.md`). That is the exception to the rule above,
not a revision of it: it was defensible only because the archive record was still an unpublished
draft and nothing external cited `fd431d8`. Two consequences stated plainly: the superseded commit
remains reachable by its hash (`github.com/…/commit/fd431d8` answers 200), so the old text is
fetchable there until GitHub garbage-collects it — the same support request already outstanding for
the pre-rewrite commits; and the dataset repository's own history carries the intermediate uploads
as commits it cannot forget.

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
| GitHub integration | software, from a release | **blocked, measured 2026-09-11:** `GET /repos/2makeitwork/paper_ai_Qos/hooks` returns an empty list both before and after the `v1.0.0` release was published, so Zenodo never installed its webhook — which is also why the repository is absent from Zenodo's GitHub settings page and why GitHub lists the Zenodo application as authorized but "never used". Everything on the repository side is in order: public, `v1.0.0` published as a non-draft, non-prerelease release, `.zenodo.json` committed at the tag, licence `mit` verified against Zenodo's licence API | the fix is on the account: re-authorize Zenodo *from* Zenodo's Applications → GitHub page (the login grant alone carries no hook permission) and check GitHub's third-party application-access restrictions for the account. If it cannot be made to work, a manual deposit of the release source archive with `upload_type: software` still mints a version identifier — at the cost of a separate record family from the one the integration would create later |

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
