# How the Notes Section Works (Plain English Guide)

This explains how your portfolio's Notes section works — the website, the
database, and the admin tool — in simple terms. Keep this for your own
reference, or use it to explain the project to someone else.

---

## 1. The three pieces of this system

Think of it like a restaurant:

| Piece | What it's like | What it actually is |
|---|---|---|
| **Frontend** | The dining room customers sit in | Your Next.js website (`localhost:3000`) — what visitors actually see |
| **Backend** | The kitchen | Your Spring Boot API (`localhost:8080`) — handles requests, talks to the database |
| **Database** | The pantry/fridge | PostgreSQL — where all your notes, resources, projects, etc. are actually stored |
| **Admin tool** (`admin.html`) | The staff-only ordering screen | A simple tool *you* use to add/edit notes — customers never see this |

None of these four pieces know how to do everything by themselves — they only
work together. If the backend isn't running, the frontend has nothing to show.
If the database isn't running, the backend has nothing to serve.

---

## 2. How they talk to each other

Every piece talks over plain web addresses (URLs), the same way your browser
talks to any website:

```
Admin tool  ──POST/GET/PUT/DELETE──▶  Backend (localhost:8080)  ──SQL──▶  Database
Frontend    ──────GET──────────────▶  Backend (localhost:8080)  ──SQL──▶  Database
```

- The **admin tool** and the **frontend** never talk to the database directly.
  They only ever talk to the **backend**.
- The **backend** is the only thing allowed to touch the database. This is
  intentional — it's the "gatekeeper" that checks requests are valid before
  anything gets saved or changed.

---

## 3. What `admin.html` actually is

`admin.html` is **not part of your real website**. It's a small, separate
tool — just one HTML file with some JavaScript in it — that you run on your
own computer only, while you're working on content. Nobody visiting your
portfolio site will ever see or use it.

It works by:
1. You open it in a browser (served locally via `npx serve`, never as a live
   public website).
2. It sends requests to your backend at `http://localhost:8080` — the exact
   same backend your real website uses.
3. Whatever you create or edit through it (a note, a resource, an edit) gets
   saved into the same database your live site reads from.

**Why a separate tool instead of building admin pages into the real site?**
Because your real site is meant for visitors, and adding "create/edit/delete"
buttons there would mean anyone could find and use them (a security risk)
unless real login/authentication is built — which is a bigger feature. The
admin tool sidesteps that for now by only running on your own machine.

---

## 4. What happens, step by step, when you add a resource

Let's trace exactly what happened when you added a YouTube link to the "LLM"
topic:

1. **You** filled in a label and URL in `admin.html` and clicked "Add."
2. **The admin tool** sent a request to your backend:
   `POST http://localhost:8080/api/v1/notes/{id}/resources/link`
   with the label, URL, and type ("YOUTUBE") attached.
3. **The backend** received this, checked it was valid (label not empty, URL
   looks real), found the "LLM" note in the database by its ID, and created
   a new row in a table called `note_resources` linking that YouTube link to
   the LLM note.
4. **The database** now has this permanently saved.
5. **The next time anyone visits** `localhost:3000` → Notes → Generative AI →
   LLM, your frontend sends a request to the backend:
   `GET http://localhost:8080/api/v1/notes/llm`
6. **The backend** looks up the LLM note *and* all its attached resources
   from the database, and sends them back as data (JSON).
7. **The frontend** receives that data and renders it as the page you see —
   title, description, subtopics, and the Resources section at the bottom.

This is the same flow every time, for every note, every resource, every edit.
Nothing is "hardcoded" — it all comes from the database, live, on every page
load.

---

## 5. A few terms explained simply

- **API** — a fixed set of "addresses" (like `/api/v1/notes`) that the
  backend listens on. Think of it as a menu of things you're allowed to ask
  the backend to do.
- **Endpoint** — one specific address on that menu, e.g.
  `GET /api/v1/notes/{slug}` is the endpoint for "give me one note's details."
- **Database table** — like a spreadsheet. `notes` is one spreadsheet (rows =
  notes), `note_resources` is another (rows = attached links/files).
- **Tree / parent-child** — each note can have a `parent`. A note with no
  parent is a top-level "Field" (like Generative AI). A note whose parent is
  a Field is a "Topic" (like RAG). This is how the drill-down navigation
  works — the frontend just asks "what are this note's children?"
- **CORS** — a browser security rule that blocks web pages from calling APIs
  on a different address unless that API explicitly allows it. This is why
  we had to configure the backend to allow requests from your admin tool's
  address.
- **Migration** (Flyway) — a numbered SQL file (`V1`, `V2`, `V3`...) that
  changes the database's structure over time, in order, so everyone's
  database ends up with the exact same tables/columns regardless of when
  they set it up.

---

## 6. Quick mental model to explain to someone else

> "My portfolio has a Next.js frontend and a Spring Boot backend with a
> PostgreSQL database. The Notes section is structured as a tree — Fields
> contain Topics, which can contain Subtopics — and every level can have
> attached resources like YouTube links, PDFs, or images. I built a small
> local admin tool that talks to the same backend API my live site uses, so
> I can add and edit content without needing a public admin panel yet."

That's genuinely an accurate, portfolio-interview-ready description of what
you've built.
