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
│   └── page.tsx     # Home page — composes the dashboard sections
├── api/
│   ├── client.ts    # apiFetch() — thin fetch wrapper around NEXT_PUBLIC_API_URL
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
│   ├── Masthead.tsx                  # Newspaper-style page header with the current date
│   ├── Gavel.tsx, MastheadRule.tsx, PaperBorder.tsx  # Decorative/layout components
├── hooks/
│   └── useChartDimensions.ts  # ResizeObserver-based container sizing for the chart
├── utils/
│   ├── formatDollars.ts         # Dollar formatting/parsing for chart labels, totals, and slider inputs
│   └── transformToHierarchy.ts  # Per-office candidate lists + active range -> office/candidate/spending-type hierarchy for d3.pack
└── types/
    └── spending.ts  # TypeScript types mirroring the backend's Pydantic response schemas
e2e/
└── candidate-range-slider.spec.ts  # Playwright spec for the range slider (needs the backend running)
```

## Local Setup

1. **Install dependencies**

   ```bash
   cd frontend
   npm install
   ```

2. **Configure the API URL**

   The app reads `NEXT_PUBLIC_API_URL` (see `src/api/client.ts`) and prefixes
   every request with it — there's no default, so it must be set. Create
   `frontend/.env.local`:

   ```bash
   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
   ```

3. **Start the backend** (see [`../backend/README.md`](../backend/README.md)) so the API is reachable at the URL above.

4. **Start the dev server**

   ```bash
   npm run dev
   ```

   The app runs at `http://localhost:3000`.

## How data flows in

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
  Zooming out of the office resets its range.

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
`http://localhost:3000`). The backend must be reachable at
`http://127.0.0.1:8000/api/v1` with 2024 data loaded, because the spec reads
expected values from the live API.

## Linting

```bash
npm run lint
```

## Notes

- `next.config.ts` enables the React Compiler (`reactCompiler: true`).
- `AGENTS.md`/`CLAUDE.md` flag that this project pins a Next.js version with
  breaking API/convention changes from what most training data assumes —
  check `node_modules/next/dist/docs/` before relying on prior Next.js
  knowledge when working in this codebase.
