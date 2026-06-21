from pydantic import BaseModel, Field
from typing import Literal


class CveFinding(BaseModel):
    vulnerability_id: str
    package: str
    installed_version: str
    fixed_version: str | None = None
    severity: str


class FeasibilityResult(BaseModel):
    id: str
    ecosystem: Literal["scala", "npm"]
    package: str
    current_version: str
    candidate_version: str | None
    status: str
    commands_run: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    patch_file: str | None = None
    log_file: str | None = None
