import json
import logging
import os
from typing import Any, Dict, List, Optional, TypedDict

from bson import ObjectId
from bs4 import BeautifulSoup  # type: ignore[import-not-found]
from langchain_openai import ChatOpenAI
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from tavily import TavilyClient

from .database import get_database
from .models import JobPost, Summary


class AgentState(TypedDict, total=False):
    job_title: str
    experience_level: str
    location: str
    search_query_id: str
    search_query_string: str
    search_attempts: int
    min_results_threshold: int
    search_results: List[str]
    crawled_pages: List[Dict[str, Any]]
    failed_urls: List[str]
    job_posts: List[Dict[str, Any]]
    analysis: Dict[str, Any]
    time_filter: Optional[str]


logger = logging.getLogger("job-intel-agent")

db = get_database()
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)


def update_status_in_db(
    search_query_id: str, status: str, error_message: Optional[str] = None
) -> None:
    logger.info("Search %s status -> %s", search_query_id, status)
    try:
        object_id = ObjectId(search_query_id)
    except Exception:  # noqa: BLE001
        return

    update_ops: Dict[str, Any] = {"$set": {"status": status}}
    if error_message is not None:
        update_ops["$set"]["error_message"] = error_message
        logger.error("Search %s error: %s", search_query_id, error_message)
    else:
        update_ops["$unset"] = {"error_message": ""}

    db["search_queries"].update_one(
        {"_id": object_id},
        update_ops,
    )


def update_failures_in_db(search_query_id: str, failures: List[str]) -> None:
    try:
        object_id = ObjectId(search_query_id)
    except Exception:  # noqa: BLE001
        return

    db["search_queries"].update_one(
        {"_id": object_id},
        {"$set": {"failed_urls": failures}},
    )


def _load_json(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def planner_node(state: AgentState) -> AgentState:
    update_status_in_db(state["search_query_id"], "PLANNING")

    next_state = dict(state)

    search_query = (
        f"\"{state['job_title']}\" job posting with {state['experience_level']} experience "
        f"in {state['location']} site:greenhouse.io OR site:lever.co OR site:linkedin.com/jobs"
    )

    time_filter = next_state.get("time_filter") or state.get("time_filter")
    time_filter_param = ""
    if time_filter:
        normalized_filter = str(time_filter).strip().lower()
        if normalized_filter == "24h":
            time_filter_param = "&tbs=qdr:d"
        elif normalized_filter == "7d":
            time_filter_param = "&tbs=qdr:w"
        elif normalized_filter == "30d":
            time_filter_param = "&tbs=qdr:m"

    search_query += time_filter_param

    next_state = dict(state)
    next_state["search_query_string"] = search_query
    next_state["search_attempts"] = next_state.get("search_attempts", 0)
    next_state.setdefault("min_results_threshold", 5)

    return next_state


def search_node(state: AgentState) -> AgentState:
    update_status_in_db(state["search_query_id"], "SEARCHING")

    query_string = state["search_query_string"]
    next_state = dict(state)
    next_state["search_attempts"] = state.get("search_attempts", 0) + 1

    try:
        response = tavily_client.search(
            query=query_string,
            search_depth="advanced",
            max_results=15,
            include_raw_content=True,
        )
        results = response.get("results", [])
        next_state["search_results"] = results
        logger.info(
            "Search %s yielded %d results", state["search_query_id"], len(results)
        )
    except Exception as exc:  # noqa: BLE001
        next_state["search_results"] = []
        failed = next_state.get("failed_urls", [])
        failed.append(f"search_error:{exc}")
        next_state["failed_urls"] = failed
        update_failures_in_db(state["search_query_id"], failed)
        logger.exception("Search %s failed during Tavily query", state["search_query_id"])

    return next_state


def refine_query_node(state: AgentState) -> AgentState:
    next_state = dict(state)
    current_query = state.get("search_query_string", "")
    refined_query = (
        f"{current_query} remote OR hybrid OR 'work from home' opportunities, "
        "include startup and enterprise listings."
    )
    next_state["search_query_string"] = refined_query
    return next_state


def crawl_extract_node(state: AgentState) -> AgentState:
    update_status_in_db(state["search_query_id"], "CRAWLING")

    next_state = dict(state)
    crawled_pages: List[Dict[str, Any]] = []
    failed_urls: List[str] = next_state.get("failed_urls", []).copy()

    for result in state.get("search_results", []):
        if isinstance(result, dict):
            try:
                url = result.get("url")
                raw_text = (
                    result.get("raw_content")
                    or result.get("content")
                    or result.get("text")
                    or result.get("markdown")
                    or ""
                )
                if not url or not raw_text:
                    continue

                apply_link = None
                soup = BeautifulSoup(raw_text, "html.parser")
                for anchor in soup.find_all("a", href=True):
                    text = anchor.get_text(strip=True).lower()
                    if any(keyword in text for keyword in ["apply", "submit", "careers"]):
                        apply_link = anchor["href"]
                        break

                crawled_pages.append(
                    {
                        "url": url,
                        "raw_text": raw_text,
                        "apply_url": apply_link,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                failed_urls.append(f"{result}:{exc}")
                logger.exception(
                    "Search %s failed to process result %s", state["search_query_id"], result
                )
        else:
            logger.warning(
                "Search %s received non-dict search result: %s",
                state["search_query_id"],
                result,
            )

    next_state["crawled_pages"] = crawled_pages
    next_state["failed_urls"] = failed_urls
    if failed_urls:
        update_failures_in_db(state["search_query_id"], failed_urls)
    logger.info(
        "Search %s crawled %d pages (failed %d)",
        state["search_query_id"],
        len(crawled_pages),
        len(failed_urls),
    )
    return next_state


def job_parsing_node(state: AgentState) -> AgentState:
    update_status_in_db(state["search_query_id"], "PARSING")

    next_state = dict(state)
    job_posts: List[Dict[str, Any]] = []

    parsing_prompt = (
        "You are an expert job description analyst. Your task is to analyze the text and determine two things: "
        "1. Is this a for a single, specific job posting? (not a list of jobs, an article, or a repo). "
        "2. Is the job still accepting applications? Look for keywords like 'no longer accepting', 'position filled', or 'closed'. "
        "If it is a single, active job posting, return a JSON object with 'is_job_posting': true, 'is_active': true, and the following fields: title, company, location, apply_url, source_site, raw_description. "
        "Otherwise, return a JSON object with 'is_job_posting': false or 'is_active': false."
    )

    for page in state.get("crawled_pages", []):
        page_content = (page.get("raw_text") or "")[:15000]
        if not page_content:
            continue

        try:
            response = llm.invoke(
                [
                    (
                        "system",
                        parsing_prompt,
                    ),
                    (
                        "user",
                        f"URL: {page.get('url')}\n"
                        f"APPLY_URL: {page.get('apply_url')}\n"
                        f"CONTENT:\n{page_content}",
                    ),
                ]
            )
            parsed_text = getattr(response, "content", None) or ""
            structured = _load_json(parsed_text)
            if structured.get("is_job_posting", False) and structured.get("is_active", False):
                structured["apply_url"] = structured.get("apply_url") or page.get("apply_url")
                structured["source_site"] = structured.get("source_site") or page.get("url")
                structured["raw_description"] = structured.get("raw_description") or page_content[:5000]
                job_posts.append(structured)
        except Exception as exc:  # noqa: BLE001
            failed = next_state.get("failed_urls", [])
            failed.append(f"parse_error:{page.get('url')}:{exc}")
            next_state["failed_urls"] = failed
            update_failures_in_db(state["search_query_id"], failed)
            logger.exception(
                "Search %s failed to parse job posting from %s",
                state["search_query_id"],
                page.get("url"),
            )

    filtered_job_posts = [
        job for job in job_posts if job.get("apply_url") not in (None, "", "N/A")
    ]
    next_state["job_posts"] = filtered_job_posts
    logger.info(
        "Search %s parsed %d job posts (filtered to %d actionable posts)",
        state["search_query_id"],
        len(job_posts),
        len(filtered_job_posts),
    )
    return next_state


def analysis_node(state: AgentState) -> AgentState:
    update_status_in_db(state["search_query_id"], "ANALYZING")

    next_state = dict(state)
    if not state.get("job_posts"):
        next_state["analysis"] = {
            "top_skills": [],
            "top_tech_stacks": [],
            "summary_text": "No job postings available for analysis.",
        }
        return next_state

    summary_prompt = (
        "Analyze the following job postings and identify the top skills, "
        "top technical stacks, and provide a concise market summary. "
        "Respond in JSON with keys: top_skills (list of strings), "
        "top_tech_stacks (list of strings), summary_text (string)."
    )

    try:
        response = llm.invoke(
            [
                ("system", summary_prompt),
                (
                    "user",
                    json.dumps({"job_posts": state["job_posts"]}, ensure_ascii=False),
                ),
            ]
        )
        parsed = _load_json(getattr(response, "content", "{}") or "{}")
        next_state["analysis"] = {
            "top_skills": parsed.get("top_skills", []),
            "top_tech_stacks": parsed.get("top_tech_stacks", []),
            "summary_text": parsed.get("summary_text", ""),
        }
    except Exception as exc:  # noqa: BLE001
        next_state["analysis"] = {
            "top_skills": [],
            "top_tech_stacks": [],
            "summary_text": f"Analysis failed: {exc}",
        }
        failed = next_state.get("failed_urls", [])
        failed.append(f"analysis_error:{exc}")
        next_state["failed_urls"] = failed
        update_failures_in_db(state["search_query_id"], failed)
        logger.exception("Search %s failed during analysis", state["search_query_id"])
    else:
        logger.info("Search %s analysis complete", state["search_query_id"])

    return next_state


def persist_node(state: AgentState) -> AgentState:
    update_status_in_db(state["search_query_id"], "PERSISTING")

    job_posts_collection = db["job_posts"]
    summaries_collection = db["summaries"]

    job_post_documents = []
    for job in state.get("job_posts", []):
        job_model = JobPost(
            search_query_id=state["search_query_id"],
            title=job.get("title", ""),
            company=job.get("company", ""),
            location=job.get("location", ""),
            apply_url=job.get("apply_url") or "",
            source_site=job.get("source_site", ""),
            raw_description=job.get("raw_description", ""),
        )
        job_post_documents.append(job_model.model_dump(by_alias=True))

    if job_post_documents:
        job_posts_collection.insert_many(job_post_documents, ordered=False)
        logger.info(
            "Search %s persisted %d job posts",
            state["search_query_id"],
            len(job_post_documents),
        )

    analysis = state.get("analysis") or {}
    if analysis:
        summary_model = Summary(
            search_query_id=state["search_query_id"],
            top_skills=analysis.get("top_skills", []),
            top_tech_stacks=analysis.get("top_tech_stacks", []),
            summary_text=analysis.get("summary_text", ""),
        )
        summaries_collection.insert_one(summary_model.model_dump(by_alias=True))
        logger.info("Search %s persisted analysis summary", state["search_query_id"])

    return state


def finish_node(state: AgentState) -> AgentState:
    return state


def should_refine_search(state: AgentState) -> str:
    min_results = state.get("min_results_threshold", 5)
    attempts = state.get("search_attempts", 0)
    results = state.get("search_results", [])

    if len(results) >= min_results:
        return "crawl_extract"

    if attempts < 3:
        return "refine_query"

    return "finish"


def is_crawl_sufficient(state: AgentState) -> str:
    if state.get("crawled_pages"):
        return "job_parsing"
    return "finish"


graph = StateGraph(AgentState)
graph.add_node("planner", planner_node)
graph.add_node("search", search_node)
graph.add_node("refine_query", refine_query_node)
graph.add_node("crawl_extract", crawl_extract_node)
graph.add_node("job_parsing", job_parsing_node)
graph.add_node("analysis", analysis_node)
graph.add_node("persist", persist_node)
graph.add_node("finish", finish_node)

graph.add_edge(START, "planner")
graph.add_edge("planner", "search")
graph.add_conditional_edges(
    "search",
    should_refine_search,
    {
        "crawl_extract": "crawl_extract",
        "refine_query": "refine_query",
        "finish": "finish",
    },
)
graph.add_edge("refine_query", "search")
graph.add_conditional_edges(
    "crawl_extract",
    is_crawl_sufficient,
    {
        "job_parsing": "job_parsing",
        "finish": "finish",
    },
)
graph.add_edge("job_parsing", "analysis")
graph.add_edge("analysis", "persist")
graph.add_edge("persist", END)
graph.add_edge("finish", END)

compiled_graph = graph.compile()


def run_agent_pipeline(search_query_id: str) -> None:
    search_record = db["search_queries"].find_one({"_id": ObjectId(search_query_id)})
    if not search_record:
        update_status_in_db(search_query_id, "FAILED", "Search query not found.")
        return

    logger.info("Starting agent pipeline for search %s", search_query_id)

    initial_state: AgentState = {
        "job_title": search_record.get("job_title", ""),
        "experience_level": search_record.get("experience_level", ""),
        "location": search_record.get("location", ""),
        "search_query_id": search_query_id,
        "search_query_string": search_record.get("search_query_string", ""),
        "search_attempts": search_record.get("search_attempts", 0),
        "min_results_threshold": search_record.get("min_results_threshold", 5),
        "search_results": [],
        "crawled_pages": [],
        "failed_urls": [],
        "job_posts": [],
        "analysis": {},
        "time_filter": search_record.get("time_filter"),
    }

    try:
        final_state = compiled_graph.invoke(initial_state)
        failures = final_state.get("failed_urls", [])
        if failures:
            update_failures_in_db(search_query_id, failures)
        logger.info("Agent pipeline completed for search %s", search_query_id)
        update_status_in_db(search_query_id, "COMPLETE")
    except Exception as exc:  # noqa: BLE001
        update_status_in_db(search_query_id, "FAILED", str(exc))
        logger.exception("Agent pipeline crashed for search %s", search_query_id)

