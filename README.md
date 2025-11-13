<div align="center">
  <h1>NextRole AI</h1>
  <p>AI-assisted job intelligence that researches open roles, parses postings, and summarizes market insights for you.</p>
</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Prerequisites](#prerequisites)
5. [Getting Started](#getting-started)
   - [1. Clone & Bootstrap](#1-clone--bootstrap)
   - [2. Environment Variables](#2-environment-variables)
   - [3. Backend Setup](#3-backend-setup)
   - [4. Frontend Setup](#4-frontend-setup)
6. [Usage](#usage)
7. [Project Structure](#project-structure)
8. [Extending the Agent](#extending-the-agent)
9. [Troubleshooting](#troubleshooting)

---

## Overview

NextRole AI automates the legwork of researching technical roles. Given a job query, the system:

- Generates a targeted search string (with optional recency filter).
- Collects search results from reputable job boards (LinkedIn Jobs, Greenhouse, Lever, etc.).
- Crawls candidate pages, filters out inactive or non-specific listings.
- Uses an LLM to extract structured job data.
- Produces a market-level summary of top skills, tech stacks, and trends.
- Surfaces everything in a modern React interface.

The project is split into a FastAPI backend (agent pipeline + REST API) and a Vite/React frontend.

---

## Key Features

- **LangGraph Agent Pipeline** orchestrating planning, search, crawl, parsing, analysis, and persistence.
- **Advanced Search & Time Filters** leveraging Tavily's API for precise, recent results.
- **LLM-powered Job Parsing** with guardrails to discard lists/articles or closed positions.
- **MongoDB Persistence** for search queries, parsed job posts, and summaries.
- **Responsive Frontend** with live polling, status updates, and actionable job tables.

---

## Architecture

```
frontend/           React (Vite) SPA
  └── src/App.jsx   Main UI with status, filters, listings & analysis

backend/
  ├── app/
  │   ├── main.py   FastAPI endpoints & CORS
  │   ├── agent.py  LangGraph/Tavily/OpenAI agent orchestration
  │   ├── models.py Pydantic models and BSON helpers
  │   └── database.py MongoDB client bootstrap
  └── requirements.txt

MongoDB Atlas or self-hosted cluster stores queries, job_posts, and summaries.
```

---

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for Vite)
- **MongoDB** URI (Atlas or local)
- **OpenAI API key** (model defaults to `gpt-4o-mini`; adjust as needed)
- **Tavily API key**

---

## Getting Started

### 1. Clone & Bootstrap

```bash
git clone https://github.com/your-org/nextrole-ai.git
cd nextrole-ai
```

### 2. Environment Variables

Create a `.env` file in `backend/` with the following keys (placeholder values shown):

```
TAVILY_API_KEY=your_tavily_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
MONGODB_URI=your_mongodb_connection_string_here
MONGODB_DB_NAME=your_database_name_here
OPENAI_MODEL=gpt-4o-mini  # Optional override
```

### 3. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs on `http://127.0.0.1:8000`. Key endpoints:

- `POST /api/search-jobs` — start a new job search.
- `GET /api/search-jobs/{search_query_id}` — poll for status/results.

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The UI runs on `http://127.0.0.1:5173` by default.

---

## Usage

1. Open the frontend and enter job title, experience band, location, and optional time filter.
2. Submit to kick off the agent pipeline; the form disables while searching.
3. The status banner updates (`PLANNING`, `SEARCHING`, `CRAWLING`, etc.).
4. Once complete, the analysis panel and job listings populate with actionable data.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── agent.py        # LangGraph pipeline & Tavily/OpenAI integrations
│   │   ├── database.py     # MongoDB client & dependency helpers
│   │   ├── main.py         # FastAPI app, routes, CORS, background tasks
│   │   └── models.py       # Pydantic models + custom ObjectId handling
│   └── requirements.txt
├── frontend/
│   ├── src/App.jsx         # React application with form, polling, tables
│   ├── src/App.css         # Dark theme styling
│   └── package.json
└── README.md
```

---

## Extending the Agent

- **Additional Sources:** Plug in more job boards by expanding the search prompt or crawling logic.
- **Enhanced Filters:** Accept salary, role level, or tech keywords and feed them into `planner_node`.
- **Notifications:** Add webhooks or email alerts when new jobs meet criteria.
- **Analytics:** Persist more metadata (salary, remote status, etc.) and enrich the summary.

Because the agent uses LangGraph, you can add new nodes (e.g., deduplication, recruiter email extraction) with minimal changes to surrounding code.

---

## Troubleshooting

| Issue | Possible Fix |
|-------|--------------|
| `Import "fastapi" could not be resolved` | Ensure the backend virtualenv is activated and dependencies installed. |
| 404 when polling search ID | Confirm the insert step succeeded (check backend logs for Mongo errors). |
| Empty results / "No job postings available" | Verify Tavily API quota, consider adjusting filters or time range. |
| LLM context errors | The agent truncates content to ~15k chars but you can reduce `page_content` slice further if necessary. |
| Mongo auth failures | Revisit `MONGODB_URI`/`MONGODB_DB_NAME` values in `.env`. |

---

| Issue | Possible Fix |
|-------|--------------|
| `Import "fastapi" could not be resolved` | Ensure the backend virtualenv is activated and dependencies installed. |
| 404 when polling search ID | Confirm the insert step succeeded (check backend logs for Mongo errors). |
| Empty results / "No job postings available" | Verify Tavily API quota, consider adjusting filters or time range. |
| **"Past 24 hours" filter returns older jobs** | **This is an expected limitation. Search engines may not have a real-time index for sites like LinkedIn that have different content for logged-in users. The time filter is a "best effort" and will be more accurate for public job boards.** |
| LLM context errors | The agent truncates content to ~15k chars but you can reduce `page_content` slice further if necessary. |

Happy hiring (or job hunting)! 🎯

