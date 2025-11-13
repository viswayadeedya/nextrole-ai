import logging

from bson import ObjectId
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agent import run_agent_pipeline
from .database import get_database
from .models import (
    JobPost,
    SearchQuery,
    SearchRequest,
    SearchResponse,
    SearchResults,
    StatusResponse,
    Summary,
)

logger = logging.getLogger("job-intel-api")

app = FastAPI(title="Job Intel Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = get_database()


@app.get("/")
async def root():
    return {"message": "Job Intel Agent API"}


@app.post("/api/search-jobs", response_model=SearchResponse)
async def search_jobs(request: SearchRequest, background_tasks: BackgroundTasks):
    search_query_data = request.model_dump()
    search_query = SearchQuery(**search_query_data)
    search_query_doc = search_query.model_dump(by_alias=True)
    search_query_doc["_id"] = ObjectId(search_query_doc["_id"])

    db["search_queries"].insert_one(search_query_doc)
    search_query_id = str(search_query_doc["_id"])

    logger.info(
        "Queued search %s for job_title='%s', experience_level='%s', location='%s'",
        search_query_id,
        request.job_title,
        request.experience_level,
        request.location,
    )

    background_tasks.add_task(run_agent_pipeline, search_query_id)

    return SearchResponse(search_query_id=search_query_id)


@app.get("/api/search-jobs/{search_query_id}", response_model=StatusResponse)
async def get_search_status(search_query_id: str):
    if not ObjectId.is_valid(search_query_id):
        raise HTTPException(status_code=400, detail="Invalid search_query_id")

    search_query = db["search_queries"].find_one({"_id": ObjectId(search_query_id)})
    if not search_query:
        raise HTTPException(status_code=404, detail="Search query not found")

    status_value = search_query.get("status", "PENDING")
    logger.info(
        "Status check for %s: %s", search_query_id, status_value
    )

    if status_value == "COMPLETE":
        job_posts_cursor = db["job_posts"].find({"search_query_id": search_query_id})
        job_posts = [JobPost.model_validate(doc) for doc in job_posts_cursor]

        summaries_cursor = db["summaries"].find({"search_query_id": search_query_id})
        summaries = [Summary.model_validate(doc) for doc in summaries_cursor]

        results = SearchResults(job_posts=job_posts, summaries=summaries)

        failed_urls = search_query.get("failed_urls", [])
        if failed_urls:
            logger.warning("Search %s completed with failures: %s", search_query_id, failed_urls)

        return StatusResponse(status=status_value, results=results, failed_urls=failed_urls or None)

    if status_value == "FAILED":
        error_message = search_query.get("error_message", "Job search failed.")
        failed_urls = search_query.get("failed_urls", [])
        logger.error(
            "Search %s failed: %s | failed_urls=%s",
            search_query_id,
            error_message,
            failed_urls,
        )
        return StatusResponse(status=status_value, message=error_message, failed_urls=failed_urls or None)

    # Include any partial failure info for in-progress states
    failed_urls = search_query.get("failed_urls", [])
    if failed_urls:
        logger.warning(
            "Search %s status %s with partial failures: %s",
            search_query_id,
            status_value,
            failed_urls,
        )

    return StatusResponse(status=status_value, failed_urls=failed_urls or None)

