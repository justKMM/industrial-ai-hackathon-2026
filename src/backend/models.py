"""The JSON the API sends, one model per type of src/frontend/src/lib/analysis/types.ts (and src/lib/backend/types.ts for the index).

Field names are camelCase on purpose, so a model and its TypeScript twin read the same. Optional fields are left out of the JSON when
they are empty (the routes use `response_model_exclude_none`), which is what an optional TypeScript field expects.
"""

# ruff: noqa: N815  (camelCase field names are the contract with the frontend)

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

StageId = Literal["vision", "profile", "regulations", "sections", "obligations", "components"]
StageStatus = Literal["pending", "running", "done", "skipped", "failed"]
AnalysisStatus = Literal["queued", "running", "done", "failed"]
RegulationLevel = Literal["device", "vehicle", "horizontal"]
Confidence = Literal["high", "medium", "low"]
Applies = Literal["certain", "likely", "possible"]
RequirementKind = Literal["design", "performance", "marking", "installation", "test-procedure", "conformity-of-production", "admin"]


class Citation(BaseModel):
    regulation: str
    version: str
    page: int
    paragraph: str


class ChecklistRequirement(BaseModel):
    id: str
    text: str
    source: Citation
    sectionTitle: str | None = None
    applies: Applies | None = None
    kind: RequirementKind | None = None


class RegulationResult(BaseModel):
    code: str
    title: str
    version: str
    level: RegulationLevel | None = None
    confidence: Confidence
    reason: str
    covers: list[str]
    requirements: list[ChecklistRequirement]


class Marker(BaseModel):
    x: float
    y: float


class ComponentResult(BaseModel):
    id: str
    name: str
    marker: Marker | None = None
    requirementIds: list[str]


class Product(BaseModel):
    name: str
    summary: str
    vehicleCategories: list[str]


class Drawing(BaseModel):
    url: str
    alt: str


class AnalysisResult(BaseModel):
    product: Product
    regulations: list[RegulationResult]
    components: list[ComponentResult]
    wholeProductRequirementIds: list[str]
    drawing: Drawing | None = None
    warnings: list[str] | None = None


class AnalysisStage(BaseModel):
    id: StageId
    status: StageStatus
    detail: str | None = None


class Analysis(BaseModel):
    id: str
    status: AnalysisStatus
    stages: list[AnalysisStage]
    createdAt: str
    error: str | None = None
    result: AnalysisResult | None = None


class StartedAnalysis(BaseModel):
    id: str


class IndexProgress(BaseModel):
    phase: Literal["cards", "parsing"]
    done: int
    total: int
    current: str | None = None


class IndexStatus(BaseModel):
    state: Literal["missing", "building", "ready", "stale", "failed"]
    parser: str
    builtAt: str | None = None
    seconds: float | None = None
    regulations: int
    total: int
    staleReasons: list[str]
    problems: list[str]
    progress: IndexProgress | None = None
    error: str | None = None


class BackendStatus(BaseModel):
    apiKey: bool
    index: IndexStatus
