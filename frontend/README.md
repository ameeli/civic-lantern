# The Civic Lantern — Frontend

## Overview

The frontend is a Next.js dashboard that visualizes campaign finance data
served by the [backend API](../backend/README.md). For a given election
cycle it shows the split between direct campaign spending and independent
("outside") expenditures, and lets you drill into per-candidate spending
with a zoomable D3 pack chart. Inside an office, a range slider scopes the
chart to candidates whose total spending falls within a chosen dollar range.

## Tech Stack

- **Framework:** Next.js 16 (App Router), React 19, TypeScript 5
- **Styling:** Tailwind CSS 4
- **Charting:** D3 7 (zoomable circle-pack chart)
- **Testing:** Vitest + React Testing Library (jsdom environment); Playwright for end-to-end tests
- **Package manager:** npm

## Project Structure

```
src/
├── app/
│   ├── layout.tsx   # Root layout: fonts, metadata
│   ├── page.tsx     # Home page — composes the dashboard sections
│   └── api/revalidate/route.ts  # POST: marks cached backend data stale (called by ingestion)
├── api/
│   ├── client.ts    # apiFetch() — cached, authenticated GET against API_URL (server-only)
│   ├── cacheTags.ts # FEC_DATA_TAG, shared by apiFetch and the revalidate route
│   └── spending.ts  # Typed calls to /election-spending and /candidate-spending
├── components/
│   ├── ElectionSpendingSection.tsx   # Inside vs. outside totals for a cycle (RSC + Suspense)
│   ├── SpendingPackChartSection.tsx  # Fetches per-candidate spending, renders the pack chart
│   ├── SpendingPackChart.tsx         # Client component: D3 zoomable circle pack
│   ├── SpendingPackChart.utils.ts    # Pure D3 class/label/text-wrap helpers for the pack chart
│   ├── SpendingPackChart.types.ts    # Pack chart node/datum types
│   ├── CandidateRangeSlider.tsx      # Dual-handle dollar-range slider for the zoomed-in office
│   ├── CandidateRangeSlider.utils.ts # Pure range clamping and candidate-count binary search
│   ├── ChartBreadcrumb.tsx           # Breadcrumb nav for the pack chart drill-down
│   ├── Masthead.tsx                  # Newspaper-style page header with the reader's current date
│   ├── Gavel.tsx, MastheadRule.tsx, PaperBorder.tsx  # Decorative/layout components
├── hooks/
│   └── useChartDimensions.ts  # ResizeObserver-based container sizing for the chart
├── utils/
│   ├── formatDollars.ts         # Dollar formatting/parsing for chart labels, totals, and slider inputs
│   ├── formatMastheadDate.ts    # Masthead date in the reader's time zone (Vercel's x-vercel-ip-timezone; America/New_York fallback)
│   └── transformToHierarchy.ts  # Per-office candidate lists + active range -> office/candidate/spending-type hierarchy for d3.pack
└── types/
    └── spending.ts  # TypeScript types mirroring the backend's Pydantic response schemas
e2e/
├── candidate-range-slider.spec.ts  # Playwright spec for the range slider (needs the backend running)
├── masthead-date.spec.ts           # Masthead shows the reader's date for their x-vercel-ip-timezone
└── masthead-title.spec.ts          # Playwright spec: masthead title stays on one line above the date at phone widths
```

## Local Setup

1. **Install dependencies**

   ```bash
   cd frontend
   npm install
   ```

2. **Configure the backend URL and key**

   `src/api/client.ts` prefixes every request with `API_URL` and sends
   `BACKEND_API_KEY` as `Authorization: Bearer <key>`. Neither has a default,
   and both are server-only (no `NEXT_PUBLIC_` prefix), so they never reach
   the browser. Create `frontend/.env.local`:

   ```bash
   API_URL=http://localhost:8000/api/v1
   BACKEND_API_KEY=local-dev-key   # must be one of the backend's API_KEYS
   ```

3. **Start the backend** (see [`../backend/README.md`](../backend/README.md)) so the API is reachable at the URL above.

4. **Start the dev server**

   ```bash
   npm run dev
   ```

   The app runs at `http://localhost:3000`.

5. **(Optional) Revalidation secret**

   `POST /api/revalidate` needs `REVALIDATE_SECRET` set (500 without it).
   Add it to `.env.local` only to exercise the route locally.

## How data flows in

Every backend call goes through `apiFetch`, a `"use cache: remote"` function:
each response is cached in the shared remote cache (Vercel Runtime Cache in
production; plain `"use cache"` would be per-instance memory), keyed by URL
and tagged `FEC_DATA_TAG`. The backend database is only queried when an entry
is missing or stale:

- After each nightly or manual ingestion, the shared
  `.github/workflows/revalidate-frontend.yml` job POSTs to `/api/revalidate`
  with `Authorization: Bearer $REVALIDATE_SECRET`, which calls
  `revalidateTag(FEC_DATA_TAG, "max")`. The next visit is served the
  stale copy while the entries it uses refresh in the background.
- `cacheLife("days")` is the fallback if that call never arrives.
- Production setup: `REVALIDATE_SECRET` in Vercel's environment variables;
  `REVALIDATE_SECRET` and `FRONTEND_URL` (the production site's origin) as
  GitHub repository secrets.

- `getElectionSpendingByCycle(cycle)` / `listCandidatesSpending(params)`
  (`src/api/spending.ts`) call the backend's `/election-spending/{cycle}` and
  `/candidate-spending` endpoints.
- `ElectionSpendingSection` and `SpendingPackChartSection` are async React
  Server Components that fetch data server-side; `ElectionSpendingSection`
  wraps each metric in its own `<Suspense>` boundary so the two totals load
  independently.
- `SpendingPackChartSection` uses `fetchAllCandidatesForOffice` to page
  through every positive-spending candidate for the cycle, once per office
  (President/Senate/House), and passes them to `SpendingPackChart`, a client
  component. Each office bubble is sized by its true total across all
  candidates. `transformToHierarchy` shows only the candidates whose total
  spending falls inside each office's range (by default, the top 30
  spenders), and splits each candidate's spending into `Inside` /
  `Outside Support` / `Outside Oppose` leaves for the D3 pack layout.
- When zoomed into an office, `CandidateRangeSlider` lets you adjust that
  range by dragging or by typing min/max amounts. The range is capped at 200
  candidates: widening one handle past the cap pulls the other handle in.
  Zooming out of the office resets its range. Pages are cached separately,
  so `fetchAllCandidatesForOffice` drops a candidate repeated across them.

## Testing

```bash
npm run test
```

Vitest with a jsdom environment and React Testing Library; see
`src/utils/__tests__/transformToHierarchy.test.ts` for an example.

End-to-end tests live in `e2e/` and run with Playwright:

```bash
npx playwright install chromium   # first run only
npm run test:e2e
```

Playwright starts `npm run dev` itself (or reuses a server already on
`http://localhost:3000`). The backend must be reachable at `API_URL`
(default `http://127.0.0.1:8000/api/v1`) with 2024 data loaded, because the
range-slider spec reads expected values from the live API, authenticating with
`BACKEND_API_KEY`; `playwright.config.ts` loads both from `.env.local`. CI loads synthetic 2024 data with
`backend/scripts/seed_e2e_data.py` (disposable databases only; see its
docstring).

## Linting

```bash
npm run lint              # ESLint
npx prettier --check .    # Formatting (see .prettierignore for exclusions)
npx next typegen          # Generate route types (PageProps etc.) for tsc
npx tsc --noEmit          # Type check
```

## Notes

- `next.config.ts` enables the React Compiler (`reactCompiler: true`) and
  Cache Components (`cacheComponents: true`), so request-time work (reading
  `searchParams`, `new Date()`) sits inside `<Suspense>` or after a
  request-time API such as `headers()` or `connection()`.
  `partialPrefetching` is off: with it on, warm-cache pages embedded a second
  ~1.5 MB copy of the chart's RSC payload.
- `AGENTS.md`/`CLAUDE.md` flag that this project pins a Next.js version with
  breaking API/convention changes from what most training data assumes —
  check `node_modules/next/dist/docs/` before relying on prior Next.js
  knowledge when working in this codebase.
