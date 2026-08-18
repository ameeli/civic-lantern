# The Civic Lantern — Frontend

## Overview

The frontend is a Next.js dashboard that visualizes campaign finance data
served by the [backend API](../backend/README.md). For a given election
cycle it shows the split between direct campaign spending and independent
("outside") expenditures, and lets you drill into per-candidate spending
with a zoomable D3 pack chart.

## Tech Stack

- **Framework:** Next.js 16 (App Router), React 19, TypeScript 5
- **Styling:** Tailwind CSS 4
- **Charting:** D3 7 (zoomable circle-pack chart)
- **Testing:** Vitest + React Testing Library (jsdom environment)
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
│   ├── ChartBreadcrumb.tsx           # Breadcrumb nav for the pack chart drill-down
│   ├── Gavel.tsx, MastheadRule.tsx, PaperBorder.tsx  # Decorative/layout components
├── hooks/
│   └── useChartDimensions.ts  # ResizeObserver-based container sizing for the chart
├── utils/
│   └── transformToHierarchy.ts  # Flat candidate spending list -> office/candidate/spending-type hierarchy for d3.pack
└── types/
    └── spending.ts  # TypeScript types mirroring the backend's Pydantic response schemas
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
- `SpendingPackChartSection` fetches up to 500 candidates for a cycle
  (sorted by outside spending) and passes them to `SpendingPackChart`, a
  client component. `transformToHierarchy` buckets candidates by office
  (President/Senate/House), groups candidates below a $1M outside-spending
  threshold into an "Others" node per office, and splits each candidate's
  spending into `Inside` / `Outside Support` / `Outside Oppose` leaves for
  the D3 pack layout.

## Testing

```bash
npm run test
```

Vitest with a jsdom environment and React Testing Library; see
`src/utils/__tests__/transformToHierarchy.test.ts` for an example.

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
