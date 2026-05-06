# LexTrace Deployment

This repo is deployed as three separate parts:

- Backend: Hugging Face Spaces Docker app
- Frontend: Vercel Next.js app
- Database: MongoDB Atlas M0 cluster

## Backend: Hugging Face Spaces

Space URL:

```txt
https://huggingface.co/spaces/ritam-05/lextrace
```

Runtime URL:

```txt
https://ritam-05-lextrace.hf.space
```

Health check:

```txt
https://ritam-05-lextrace.hf.space/health
```

Expected healthy response:

```json
{
  "status": "active",
  "database": "connected",
  "embedding_model": "loaded",
  "device": "cpu"
}
```

The Space uses the root `Dockerfile` and runs:

```sh
uvicorn backend.app:app --host 0.0.0.0 --port 7860
```

Set these secrets in Hugging Face:

1. Open the Space.
2. Go to **Settings**.
3. Scroll to **Variables and secrets**.
4. Add secrets:

```txt
MONGO_URI=<MongoDB Atlas connection string>
GROQ_API_KEY=<Groq API key>
```

After changing secrets, restart or rebuild the Space.

## Frontend: Vercel

Production URL:

```txt
https://lextrace-three.vercel.app
```

Vercel import settings:

```txt
Repository: ritam-05/lextrace
Branch: main
Root Directory: frontend
Framework Preset: Next.js
```

Set this Vercel environment variable:

```txt
FASTAPI_BASE_URL=https://ritam-05-lextrace.hf.space
```

The frontend calls backend APIs through Next.js route handlers under `/api/*`.

Note: Vercel's embedded dashboard preview may show `403 Forbidden` because the app sets:

```txt
frame-ancestors 'none'
```

This blocks iframe previews, but the production URL itself works.

## Database: MongoDB Atlas

The database is already deployed as a MongoDB Atlas M0 cluster.

Required Atlas setup:

- Database user must have read/write access.
- Network Access must allow Hugging Face Spaces and Vercel to connect.
- For the simplest deployment, allow:

```txt
0.0.0.0/0
```

The backend verifies database connectivity through `/health`.

## Deployment Checks

Backend and database:

```sh
curl https://ritam-05-lextrace.hf.space/health
```

Frontend:

```sh
curl https://lextrace-three.vercel.app
```

Frontend upload proxy:

```sh
curl -X POST https://lextrace-three.vercel.app/api/upload
```

Without a PDF file, the expected response is:

```json
{
  "error": "Missing required 'file' field",
  "message": "Missing required 'file' field",
  "status": 400
}
```

## Current Notes

- The Hugging Face backend is currently running on CPU.
- Upload/RAG processing can take several minutes on CPU.
- Frontend upload timeout is configured for 5 minutes.
- Do not commit `.env` or secrets to Git.
