# Enterprise Knowledge Agent — frontend

The Next.js frontend for the Enterprise Knowledge Agent (Phase 5). It is a single
page that calls the FastAPI gateway's `POST /api/chat` and renders grounded
answers with their citations.

## Running it

Start the gateway first (from the repository root), then the frontend:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The gateway defaults to
`http://127.0.0.1:8000`; set `NEXT_PUBLIC_API_BASE_URL` to point somewhere else.
No `.env` file is needed for the default local setup.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Development server |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint |
| `npm run test` | Vitest, for the pure citation logic |

## Citation rendering

The API returns the answer with its inline `【N:M†source】` markers intact, plus a
span (`start_index`/`end_index`) per citation. `lib/citations.ts` splits the
answer into ordered text and citation segments so the UI can replace each marker
with a numbered link. It is a pure function and is covered by
`lib/citations.test.ts`.
