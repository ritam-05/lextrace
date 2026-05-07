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

## Set Up On A New PC

Follow these steps when setting up LexTrace locally on a fresh Windows PC.

### 1. Install Required Software

Install these first:

- Git: https://git-scm.com/downloads
- Python 3.11: https://www.python.org/downloads/
- Node.js LTS: https://nodejs.org/
- MongoDB Atlas account or access to the existing Atlas connection string
- Tesseract OCR for Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Poppler for Windows: https://github.com/oschwartz10612/poppler-windows/releases

After installing Python and Node, open a new PowerShell window and check:

```sh
git --version
python --version
node --version
npm --version
```

Python should be 3.11.x. Node should be an active LTS version.

### 2. Clone The Repository

Choose a folder where you keep projects, then run:

```sh
git clone https://github.com/ritam-05/lextrace.git
cd lextrace
```

### 3. Create The Backend Virtual Environment

From the repo root:

```sh
python -m venv venv311
.\venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, run PowerShell as your user and allow local scripts:

```sh
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then close and reopen PowerShell, go back to the repo, and activate again:

```sh
cd path\to\lextrace
.\venv311\Scripts\Activate.ps1
```

### 4. Configure Backend Environment Variables

Create a root `.env` file:

```txt
MONGO_URI=<MongoDB Atlas connection string>
GROQ_API_KEY=<Groq API key>
```

The backend needs both values. `MONGO_URI` stores extraction and verification data. `GROQ_API_KEY` is used by the RAG generation pipeline.

### 5. Make OCR Tools Available

Tesseract and Poppler must be available in `PATH` for OCR/PDF fallback workflows.

Typical Windows paths to add:

```txt
C:\Program Files\Tesseract-OCR
C:\path\to\poppler\Library\bin
```

After updating `PATH`, open a new PowerShell window and check:

```sh
tesseract --version
pdftoppm -v
```

### 6. Start The Backend

From the repo root, with the virtual environment active:

```sh
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

The first startup can take time because the embedding model is downloaded and loaded.

Check the backend:

```sh
curl http://localhost:8000/health
```

Expected shape:

```json
{
  "status": "active",
  "database": "connected",
  "embedding_model": "loaded",
  "device": "cpu"
}
```

Keep this backend terminal running.

### 7. Install Frontend Dependencies

Open a second PowerShell window:

```sh
cd path\to\lextrace\frontend
npm install
```

### 8. Configure Frontend Environment Variables

Create `frontend/.env.local`:

```txt
FASTAPI_BASE_URL=http://localhost:8000
```

This tells the Next.js API routes to call your local FastAPI backend.

### 9. Start The Frontend

From `frontend/`:

```sh
npm run dev
```

If PowerShell blocks `npm`, use:

```sh
npm.cmd run dev
```

Open the local app:

```txt
http://localhost:3000
```

### 10. Verify The Full Local Flow

1. Open `http://localhost:3000`.
2. Upload a judgment PDF.
3. Wait for extraction and RAG processing to finish.
4. Review all extracted fields and action items.
5. Click Done after every item is verified.
6. Confirm the dashboard opens with the verified judgment data.

### 11. Useful Local Checks

Frontend typecheck:

```sh
cd frontend
npm.cmd run typecheck
```

Frontend production build:

```sh
cd frontend
npm.cmd run build
```

Git status before committing:

```sh
git status --short
```

Generated folders such as `frontend/node_modules/`, `frontend/.next/`, and `venv311/` should stay untracked.

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
