# License for the code

**MIT License** — applies to the executable tooling in `scripts/`
(the collection, anonymization, verification, mirror and watcher code). A few local-only
repository tools under `tools/` are under these same terms but are not part of the
published set. Text,
tables, figures and evidence data are covered by `LICENSE-content.md` instead.

Copyright (c) 2026 2makeitwork

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

One obligation that is not legal but is ours: if you re-run these scripts on your
own installation, do not publish the raw output of `scripts/collect_evidence.sh`
or the mirror tree — they contain local paths and conversation identifiers.
Publish only what `scripts/anonymize.py` emits, and keep its self-audit passing
(it exits nonzero if a personal pattern survives).
