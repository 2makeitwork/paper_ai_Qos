# User statements (verbatim, from IDE prompt history)

Source: `state.vscdb` table `ItemTable`, keys `lingma.chat.localHistory.*`
(the durable store for prompt titles + timestamps; the transcript JSONL does not
persist every prompt — a persistence inconsistency noted in the report).

## Statement 1 — 2026-09-09 14:21:01 AWST — session `sess-03`

> ​ws-C-cache.txt​ the return code may be inconsistent. On the UI, I see at least 3 times timeout with the retry button in the past 60mins.

## Statement 2 — 2026-09-09 14:52:52 AWST — session `sess-04`

> 2 failure modes. Time out: you have a messages that reads Response timeout. Click to resume or switch to another model and try again. plus a button to push, after pushing, the button is replaced by 'working...'
> quota issue: there's no button (a different message) you have to type in something. I never resubmit the complete meg. I always use 'continue, retry, try again'
