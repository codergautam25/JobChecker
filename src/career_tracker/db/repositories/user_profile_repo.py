"""User profile repository — CRUD operations for user_profiles table."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import structlog

from career_tracker.db.database import DatabaseManager, get_database

logger = structlog.get_logger(__name__)


class UserProfileRepository:
    """Data access object for user profiles.

    Typically a single profile exists per installation, but the schema
    supports multiple profiles for future multi-user scenarios.
    """

    def __init__(self, db: DatabaseManager | None = None) -> None:
        self._db = db or get_database()

    def create(self, profile: dict) -> dict:
        """Insert a new user profile."""
        sql = """
            INSERT INTO user_profiles
                (id, name, email, phone, linkedin_url, github_url,
                 portfolio_url, target_roles, target_locations, min_salary,
                 preferred_industries, skills, experience, education,
                 certifications, projects, publications, awards, languages, social_links, parsed_files,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = datetime.utcnow().isoformat()
        params = (
            profile["id"], profile["name"], profile["email"],
            profile.get("phone"), profile.get("linkedin_url"),
            profile.get("github_url"), profile.get("portfolio_url"),
            json.dumps(profile.get("target_roles", [])),
            json.dumps(profile.get("target_locations", [])),
            profile.get("min_salary"),
            json.dumps(profile.get("preferred_industries", [])),
            json.dumps(profile.get("skills", [])),
            json.dumps(profile.get("experience", [])),
            json.dumps(profile.get("education", [])),
            json.dumps(profile.get("certifications", [])),
            json.dumps(profile.get("projects", [])),
            json.dumps(profile.get("publications", [])),
            json.dumps(profile.get("awards", [])),
            json.dumps(profile.get("languages", [])),
            json.dumps(profile.get("social_links", [])),
            json.dumps(profile.get("parsed_files", [])),
            now, now,
        )
        self._db.execute_write(sql, params)
        logger.info("user_profile.created", id=profile["id"])
        return profile

    def get_by_id(self, profile_id: str) -> Optional[dict]:
        """Fetch a user profile by ID."""
        rows = self._db.execute("SELECT * FROM user_profiles WHERE id = ?", (profile_id,))
        if not rows:
            return None
        return self._parse_json_fields(rows[0])

    def get_default(self) -> Optional[dict]:
        """Fetch the first (default) user profile."""
        rows = self._db.execute(
            "SELECT * FROM user_profiles ORDER BY created_at ASC LIMIT 1"
        )
        if not rows:
            return None
        return self._parse_json_fields(rows[0])

    def update(self, profile_id: str, updates: dict) -> None:
        """Update fields of an existing user profile."""
        # Serialize JSON array fields
        json_fields = {
            "target_roles", "target_locations", "preferred_industries", "skills",
            "experience", "education", "certifications", "projects",
            "publications", "awards", "languages", "social_links", "parsed_files"
        }
        processed = {}
        for key, value in updates.items():
            if key in json_fields and isinstance(value, (list, dict)):
                processed[key] = json.dumps(value)
            else:
                processed[key] = value

        processed["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in processed)
        params = list(processed.values()) + [profile_id]

        self._db.execute_write(
            f"UPDATE user_profiles SET {set_clause} WHERE id = ?",
            tuple(params),
        )
        logger.info("user_profile.updated", id=profile_id)

    @staticmethod
    def _parse_json_fields(row: dict) -> dict:
        """Parse JSON array fields in a profile row."""
        result = dict(row)
        for field in (
            "target_roles", "target_locations", "preferred_industries", "skills",
            "experience", "education", "certifications", "projects",
            "publications", "awards", "languages", "social_links", "parsed_files"
        ):
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    result[field] = {} if field == "social_links" else []
            else:
                result[field] = {} if field == "social_links" else []
        return result
