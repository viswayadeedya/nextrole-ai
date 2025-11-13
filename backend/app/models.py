from datetime import datetime
from typing import Any, List, Optional

from bson import ObjectId
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)
from typing_extensions import Annotated


def _validate_object_id(value: Any) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError("Invalid ObjectId")


PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(_validate_object_id),
    PlainSerializer(lambda v: str(v), return_type=str),
    WithJsonSchema({"type": "string", "pattern": "^[0-9a-fA-F]{24}$"}),
]


class SearchRequest(BaseModel):
    job_title: str
    experience_level: str
    location: str


class SearchQuery(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
    job_title: str
    experience_level: str
    location: str
    status: str = Field(default="PENDING")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobPost(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
    search_query_id: str
    title: str
    company: str
    location: str
    apply_url: str
    source_site: str
    raw_description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Summary(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
    search_query_id: str
    top_skills: List[str]
    top_tech_stacks: List[str]
    summary_text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SearchResponse(BaseModel):
    search_query_id: str


class SearchResults(BaseModel):
    job_posts: List[JobPost]
    summaries: List[Summary]


class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    results: Optional[SearchResults] = None
    failed_urls: Optional[List[str]] = None

