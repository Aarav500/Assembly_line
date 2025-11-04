from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator
from security.sanitization import sanitize_html, sanitize_plain_text


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    email: EmailStr
    bio: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        # Enforce normalized safe username
        return sanitize_plain_text(v)

    @field_validator("bio")
    @classmethod
    def sanitize_bio(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Allow safe subset of HTML
        return sanitize_html(v)


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=20000)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        return sanitize_plain_text(v)

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        # Remove control chars, normalize whitespace, no HTML in titles
        return sanitize_plain_text(v)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        # Allow safe subset of HTML to avoid XSS
        return sanitize_html(v)


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: str = Field(..., min_length=1, max_length=100)

    @field_validator("q")
    @classmethod
    def sanitize_q(cls, v: str) -> str:
        # Plain text only for search term
        return sanitize_plain_text(v)


class DNSLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    host: str = Field(..., min_length=1, max_length=253)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        v = sanitize_plain_text(v)
        # Basic domain or IPv4 validation; reject options-like inputs
        import re

        if v.startswith("-"):
            raise ValueError("host cannot start with hyphen")
        if ".." in v:
            raise ValueError("invalid host")

        ipv4_re = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
        domain_re = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?:\.(?!-)[A-Za-z0-9-]{1,63})+$")

        def valid_ipv4(addr: str) -> bool:
            if not ipv4_re.match(addr):
                return False
            parts = addr.split(".")
            return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

        if not (valid_ipv4(v) or domain_re.match(v)):
            raise ValueError("invalid host")
        return v

