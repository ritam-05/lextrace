---
title: LexTrace
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# LexTrace

## Links

- Frontend app: https://lextrace-three.vercel.app
- Hugging Face Space: https://huggingface.co/spaces/ritam-05/lextrace
- Backend runtime: https://ritam-05-lextrace.hf.space
- Backend health check: https://ritam-05-lextrace.hf.space/health
- GitHub repository: https://github.com/ritam-05/lextrace
- Hugging Face Spaces config reference: https://huggingface.co/docs/hub/spaces-config-reference

## What LexTrace Does

LexTrace is a judgment review and compliance-tracking application. It lets a user upload a court judgment PDF, extracts important case information, identifies court directions and required compliance actions, asks a reviewer to verify the extracted data, and then generates a trusted dashboard view for follow-up action.

The app is split into three deployed parts:

- Frontend: Next.js app on Vercel.
- Backend: FastAPI app running as a Hugging Face Docker Space.
- Database: MongoDB Atlas, used for uploaded document metadata, extraction results, verification records, and dashboard data.

## How The App Works

1. Upload a judgment PDF from the frontend.
2. The frontend sends the file to a Next.js API route.
3. The Next.js route forwards the file to the FastAPI backend.
4. The backend extracts text from the PDF, using OCR fallback when needed.
5. Regex extraction identifies structured metadata such as case number, court, judge, parties, and order date.
6. RAG extraction analyzes the judgment text for key directions, compliance requirements, timelines, departments, and appeal risk.
7. The arbitration layer compares regex and RAG outputs and prepares fields for human review.
8. Extraction and arbitration results are saved in MongoDB.
9. The reviewer checks each field and action item in the review screen.
10. After all items are approved, edited, or rejected, the reviewer submits the verified judgment.
11. Verified data is saved and shown in the dashboard.

## Main User Flow

- Upload page: upload a judgment PDF and start processing.
- Review page: inspect extracted metadata, directions, compliance steps, and timelines against the PDF.
- Dashboard page: view verified case summary, directives, required actions, department-wise tasks, timelines, and appeal analysis.

## Backend

The backend is a FastAPI service under `backend/`.

Important files:

- `backend/app.py`: FastAPI app setup, model loading, route registration, and `/health`.
- `backend/routes/rag_test.py`: upload and extraction pipeline used by the deployed app.
- `backend/routes/verification.py`: review, approval, rejection, and reset endpoints.
- `backend/rag_engine/generator.py`: RAG prompt and structured generation logic.
- `backend/services/regex_extractor.py`: rule-based metadata extraction.
- `backend/services/arbitrator.py`: arbitration between regex and RAG outputs.
- `backend/database.py`: MongoDB connection helper.

The Hugging Face Space uses the root `Dockerfile` and runs:

```sh
uvicorn backend.app:app --host 0.0.0.0 --port 7860
```

Health check:

```txt
GET /health
```

Expected response:

```json
{
  "status": "active",
  "database": "connected",
  "embedding_model": "loaded",
  "device": "cpu"
}
```

## Frontend

The frontend is a Next.js app under `frontend/`.

Important files:

- `frontend/app/page.tsx`: upload landing page.
- `frontend/app/review/[docId]/page.tsx`: review route.
- `frontend/app/dashboard/page.tsx`: verified dashboard route.
- `frontend/app/api/*`: Vercel-side API proxy routes.
- `frontend/components/review/*`: human review UI.
- `frontend/components/dashboard/*`: dashboard sections.
- `frontend/store/reviewStore.ts`: review workflow state.
- `frontend/lib/apiClient.ts`: frontend API client.

The frontend calls its own `/api/*` route handlers first. Those route handlers forward requests to the FastAPI backend through `FASTAPI_BASE_URL`.

## Required Environment Variables

Backend Hugging Face Space secrets:

```txt
MONGO_URI=<MongoDB Atlas connection string>
GROQ_API_KEY=<Groq API key>
```

Frontend Vercel environment variable:

```txt
FASTAPI_BASE_URL=https://ritam-05-lextrace.hf.space
```

Do not commit `.env` files or secrets.

## Local Development

Backend:

```sh
pip install -r requirements.txt
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```sh
cd frontend
npm install
npm run dev
```

Useful frontend checks:

```sh
cd frontend
npm run typecheck
npm run build
```

On Windows PowerShell, if `npm` is blocked by script execution policy, use:

```sh
npm.cmd run typecheck
npm.cmd run build
```

## Deployment

Hugging Face Space:

- Repo path: `https://huggingface.co/spaces/ritam-05/lextrace`
- SDK: Docker
- Port: `7860`
- Required root files: `README.md`, `Dockerfile`, `requirements.txt`, and `backend/`

Vercel:

- Repository: `ritam-05/lextrace`
- Branch: `main`
- Root Directory: `frontend`
- Framework Preset: Next.js
- Environment variable: `FASTAPI_BASE_URL=https://ritam-05-lextrace.hf.space`

## Troubleshooting

Configuration error on Hugging Face:

- Make sure root `README.md` exists.
- Keep the YAML front matter at the very top of the file.
- Make sure it includes `sdk: docker` and `app_port: 7860`.

Service unavailable:

- The Space may still be building or starting.
- The backend may be loading the embedding model.
- Check `/health`.
- Check Hugging Face build and runtime logs.

No arbitration result found:

- The review page has a document ID, but MongoDB does not have the matching extraction record.
- Re-upload the PDF if the document came from an old browser session.
- Confirm the frontend and backend point to the same database.

Vercel build failure:

- Run `npm.cmd run typecheck` and `npm.cmd run build` inside `frontend/`.
- Confirm Vercel Root Directory is set to `frontend`.
- Confirm `FASTAPI_BASE_URL` is set in Vercel.

Large file rejected by Hugging Face:

- Do not commit `frontend/node_modules/`, `frontend/.next/`, `frontend/out/`, or `*.tsbuildinfo`.
- These generated files are ignored by `.gitignore`.
