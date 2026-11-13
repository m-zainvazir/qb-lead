"""Request and response schemas. Every input model rejects unknown fields."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- /me -----------------------------------------------------------------------
class Company(BaseModel):
    id: UUID
    name: str
    type: Literal["freelancer", "agency"]
    role: Literal["owner", "admin", "member"]
    is_internal: bool


class PlatformAdminInfo(BaseModel):
    level: Literal["super", "support"]
    mfa_verified: bool


class Me(BaseModel):
    id: UUID
    email: str
    companies: list[Company]
    platform_admin: PlatformAdminInfo | None


# --- tenants -------------------------------------------------------------------
class CreateCompany(Input):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[^\x00-\x1f\x7f]+$")
    type: Literal["freelancer", "agency"]


class CreatedCompany(BaseModel):
    id: UUID


# --- team ----------------------------------------------------------------------
class Member(BaseModel):
    user_id: UUID
    email: str
    role: Literal["owner", "admin", "member"]
    joined_at: datetime


class ChangeRole(Input):
    role: Literal["owner", "admin", "member"]


class InvitationOut(BaseModel):
    id: UUID
    email: str
    role: Literal["admin", "member"]
    expires_at: datetime
    created_at: datetime


class Team(BaseModel):
    members: list[Member]
    invitations: list[InvitationOut]


# --- invitations -----------------------------------------------------------------
class CreateInvitation(Input):
    email: EmailStr = Field(max_length=320)
    role: Literal["admin", "member"]


class InvitationToken(Input):
    token: str = Field(min_length=20, max_length=200, pattern=r"^[A-Za-z0-9_\-]+$")


class InvitationPreview(BaseModel):
    company_name: str
    role: Literal["admin", "member"]
    email: str
    is_valid: bool


class AcceptedInvitation(BaseModel):
    tenant_id: UUID
