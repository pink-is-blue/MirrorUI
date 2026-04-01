from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    url: str


class BenchmarkRequest(BaseModel):
    urls: Dict[str, str] = Field(default_factory=dict)


class DOMNode(BaseModel):
    node_id: str
    tag: str
    text: str = ""
    classes: List[str] = Field(default_factory=list)
    attrs: Dict[str, str] = Field(default_factory=dict)
    styles: Dict[str, str] = Field(default_factory=dict)
    box: Dict[str, float] = Field(default_factory=dict)
    children: List[str] = Field(default_factory=list)
    parent_id: Optional[str] = None
    visible: bool = True
    depth: int = 0
    order: int = 0
    interactive: bool = False
    role_hint: str = ""


class CapturePayload(BaseModel):
    url: str
    title: str
    screenshot_path: str
    viewport: Dict[str, int]
    html: str
    dom_nodes: List[DOMNode]
    challenge_detected: bool = False
    challenge_reason: str = ""


class VisualRegion(BaseModel):
    region_id: str
    role: str
    x: int
    y: int
    w: int
    h: int
    score: float = 0.0


class LayoutGraph(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class Section(BaseModel):
    section_id: str
    role: Literal["header", "navbar", "hero", "cards", "form", "footer", "content"]
    node_ids: List[str] = Field(default_factory=list)
    repeated: bool = False


class Action(BaseModel):
    action: str
    target: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class GenerationCandidate(BaseModel):
    candidate_id: str
    rationale: str
    files: Dict[str, str]
    artifacts: Dict[str, Any] = Field(default_factory=dict)


class GenerationResult(BaseModel):
    title: str
    screenshot_path: str
    files: Dict[str, str]
    layout: Dict[str, Any]
    actions: List[Action]
    comparison: Dict[str, Any]
    metrics: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)
    challenge_detected: bool = False
    challenge_reason: str = ""


class EditorUpdateRequest(BaseModel):
    node_id: str
    text: Optional[str] = None
    href: Optional[str] = None
    image_src: Optional[str] = None
    class_name: Optional[str] = None


class EditorUpdateResponse(BaseModel):
    ok: bool
    updated_node: Dict[str, Any]
    files: Dict[str, str]
