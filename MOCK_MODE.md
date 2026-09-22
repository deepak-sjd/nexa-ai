# Mock image generation — setup & test

Lets you build/test the entire image UI (pending, success, errors, retry,
gallery, lightbox) with **zero Gemini calls, zero cost, no quota used**.
Your existing `GEMINI_API_KEY` is untouched — chat and RAG still use it as
before; this only short-circuits the image-generation call.

## Files in this update
- `backend/app/core/config.py` — modified, 2 new settings
- `backend/app/services/image_service.py` — modified
- `backend/app/services/mock_images.py` — new (3 tiny embedded placeholder
  PNGs, no new dependency, nothing downloaded at runtime)

Same apply method as before: drop these into your project at the matching
paths, overwriting the two modified files.

## 1. Turn it on

Add to `backend/.env`:

```
MOCK_IMAGE_GENERATION=true
```

Restart the backend:

```bash
cd backend
uvicorn app.main:app --reload
```

You should see this line in the terminal at startup:

```
Image generation is running in MOCK mode (MOCK_IMAGE_GENERATION=true). Set it to false to generate real images.
```

If you don't see it, the `.env` change wasn't picked up — double check the
line is in `backend/.env` (not `.env.example`) with no quotes or typos, and
that you restarted uvicorn.

## 2. Test it — quick curl check first

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/images/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"a red fox","conversation_id":1}' | head -c 200
```

Should return instantly (~1.5s) with `"image_url": "/api/v1/images/files/..."`.
No Gemini traffic, no quota used.

## 3. Test it in the UI

Everything works exactly as before — type a prompt, hit Enter. It'll resolve
in ~1.5s with one of 3 placeholder images (a gradient with a circle, triangle,
or square). Same prompt always returns the same placeholder, so retry/
regenerate behave predictably while you test.

## 4. Trigger every error state on demand

Put one of these anywhere in your prompt (case-insensitive) to force that
outcome — no need to wait for a real rate limit or guess at network failures:

| Type this in the prompt | What happens |
|---|---|
| `mock:429` | Rate-limit error card (429), same message as the real one |
| `mock:error` | Generic "Couldn't create the image" error card |
| `mock:slow` | Takes ~8s — use this to test the elapsed timer and the Cancel button |
| anything else | Succeeds after ~1.5s |

Example: type `a castle mock:429` and hit Enter → you should see the red
error card with **Try again**. Click it, and since the trigger word is gone
after a retry with a different prompt, a normal retry (same prompt) will
still hit the same trigger — type a new prompt without `mock:429` to see it
succeed.

Suggested test pass:
1. Normal prompt → pending card → image appears, Download/View/Regenerate work.
2. `mock:slow` → confirm the timer counts up, click **Cancel**, confirm the
   "Cancelled" card appears (not the red error style).
3. `mock:429` → confirm the red error card + **Try again**, click it with a
   normal prompt to confirm retry recovers.
4. `mock:error` → same, for the generic error path.
5. Send a normal chat message right after an image → confirms the chat
   history fix is working (no base64 dumped into the next Gemini call).

## 5. Turn it back off

When you're ready to test against real Gemini (with billing/budget cap set
up), remove the line from `.env` or set:

```
MOCK_IMAGE_GENERATION=false
```

and restart uvicorn. Everything else about the feature is identical either
way — the frontend can't tell the difference.

## What I verified vs. didn't

**Verified for real** (not just read): I ran the actual `image_service.py`
mock code path in a Python sandbox with only `google.genai` and `tenacity`
stubbed out (so real backend code executes, just without those two
packages installed there). 15 checks passed: no API key required, the real
`genai.Client()` is never constructed, returned bytes are valid PNGs (checked
the PNG magic bytes after base64-decoding), the delay is real (measured),
same prompt returns the same image, all three magic triggers raise the
correct exception type with the correct message, and `mock:slow` genuinely
takes ~8s.

**Not verified:** the full FastAPI route with this change (no FastAPI in my
sandbox, same limitation as before) — but the route calls
`image_service.generate_image()` exactly as it did before, so nothing about
the route itself changed.
