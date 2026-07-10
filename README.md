# NovelCraft Personal Studio

AI content production workbench for personal novel writing and small creator teams.

This repository starts the M1 vertical slice from the project documentation:

- Unified content model
- Bootstrap workflow from idea to reviewed first chapter
- Human title selection gate
- AI call tracing and budget accounting
- Versioned content save/restore
- React workbench for wizard, progress, review, editor, and costs

Project progress is tracked in [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md).

## Documentation

- Product idea: [docs/IDEA.md](docs/IDEA.md)
- Development documentation index: [docs/NovelCraft-开发文档/README-文档索引.md](docs/NovelCraft-开发文档/README-文档索引.md)
- Historical documentation archive: [docs/archive/README.md](docs/archive/README.md)
- Project progress: [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md)

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
