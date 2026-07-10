# NovelCraft Personal Studio

AI content production workbench for personal novel writing and small creator teams.

This repository starts the M1 vertical slice from the project documentation:

- Unified content model
- Bootstrap workflow from idea to reviewed first chapter
- Human title selection gate
- AI call tracing and budget accounting
- Versioned content save/restore
- React workbench for wizard, progress, review, editor, and costs

## Local Development

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal. The frontend expects the API at `http://127.0.0.1:8000`.

## Current Scope

This is a functional development foundation, not the full M1 gate yet. Provider calls are mocked through the AI Gateway interface so the workflow, tracing, versions, and UI can be developed without spending model credits.
