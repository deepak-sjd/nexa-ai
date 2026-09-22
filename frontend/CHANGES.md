# NEXA AI — image generation UI + backend hardening

Unzip at your project root (the folder containing `frontend/` and `backend/`).
Only changed or new files are included — everything else is untouched.

## Apply

```bash
# backend
cd backend
alembic upgrade head          # adds messages.image_filename (nullable, instant)
uvicorn app.main:app --reload

# frontend (optional: point at a different API)
cd frontend
cp .env.example .env          # then edit VITE_API_BASE_URL if needed
npm run dev
```

The frontend works with your **current** backend too (it understands both the
old `image_base64` response and the new `image_url` one), so you can apply the
two halves separately. If you apply only ONE backend change, make it
`routes/message.py` — without it, a generated image poisons the next chat turn.

## Files

### Frontend (`frontend/`)
| File | What |
|---|---|
| `src/App.jsx` | **Modified** (+178 / −29). Image toggle + `/image` command, renders image/pending/error messages, stable React keys, scroll fix, no payload logging. |
| `src/ImageGeneration.css` | New. All image styles (imported by App.jsx; App.css untouched). |
| `src/services/api.js` | New. `API_BASE_URL` (from `VITE_API_BASE_URL`) + `generateImage()` with timeout/cancel/error mapping. |
| `src/hooks/useImageGeneration.js` | New. Pending → success / error / cancelled, retry. |
| `src/utils/imageMessage.js` | New. `/image` parsing, history normalisation (incl. old base64 rows), download. |
| `src/components/GeneratedImage.jsx` | New. Image card: Download, View, Regenerate. |
| `src/components/ImageLightbox.jsx` | New. Full-screen viewer (portal, Esc, focus trap). |
| `src/components/ImageStatusCards.jsx` | New. Pending card (timer + Cancel) and error card (Try again). |
| `src/components/ImageIcons.jsx` | New. Inline SVG icons. |
| `.env.example` | New. |

### Backend (`backend/`)
| File | What |
|---|---|
| `app/api/routes/message.py` | **Fix:** image messages are replaced by a short note before being sent to Gemini as history. |
| `app/api/routes/images.py` | Rewritten: validates the conversation *before* generating, releases the DB connection during generation, stores the image on disk, saves the user prompt + image in one transaction, auto-titles the conversation, serves `GET /images/files/{name}` with cache headers. |
| `app/services/image_storage.py` | New. Save / resolve (path-traversal-safe) / delete. |
| `app/models/message.py` | + `image_filename` column. |
| `alembic/versions/d4e5f6a7b8c9_…py` | New migration (revises `c3d4e5f6a7b8`). |
| `app/schemas/message.py` | Messages expose `image_url` (computed). |
| `app/api/routes/conversations.py` | Deleting a conversation also deletes its image files. |
| `app/core/config.py` | + `generated_images_dir`, `max_image_prompt_chars` (both have defaults). |

## Smoke test the backend (I could not run it — see below)

Use Swagger at http://127.0.0.1:8000/docs (easiest on Windows), or:

1. `POST /api/v1/images/generate` `{"prompt":"a red fox","conversation_id":1}`
   → response has `image_url` and `message_id`, **no** base64.
2. Open `http://127.0.0.1:8000<image_url>` → the image (`Cache-Control: private, max-age=31536000, immutable`).
3. `GET /api/v1/conversations/1/messages` → a `user` row (the prompt) then an
   `assistant` row with `image_url`; small payload.
4. Send a normal chat message in that conversation → works (history has a
   one-line note, not the image).
5. `GET /api/v1/images/files/..%2f..%2f.env` → 404.
6. Delete the conversation → the file disappears from `data/generated_images/`.
7. `POST /images/generate` with `"conversation_id": 999999` → 404 (and no Gemini call is made).

## What was and wasn't verified

**Verified (headless Chromium, mocked API):** 50 end-to-end checks on the real
built app — generate / pending / cancel / retry / errors (429, network,
validation), legacy base64 history, new `image_url` history, lightbox +
focus handling, download filename, text-chat regression, 390px mobile, no
horizontal overflow. ESLint result identical to your baseline (10 errors,
1 warning that already existed); new files: 0.

**Verified (plain Python, no framework):** 23 unit checks on `image_storage.py`
(path traversal, atomic save, cleanup) and on the history sanitiser (a 2 MB
base64 message becomes 61 characters).

**NOT verified:** the FastAPI/SQLAlchemy wiring of the backend files (no
FastAPI in my sandbox — they compile and were reviewed line by line, but not
executed), the migration against Postgres, a real Gemini call, browsers other
than Chromium, and the microphone.

## Notes
- Old image messages already in your database (base64 in `content`) still
  render, and are stripped from LLM history. They are not converted to files.
- Add `data/generated_images/` to `backend/.gitignore`.
- Cancel stops the browser waiting; the server may still finish and save the
  image (a sync FastAPI route isn't interrupted by a client disconnect).
- Image URLs are unguessable but not access-controlled — add auth first
  (see review), then serve them through an authenticated route or signed URLs.
