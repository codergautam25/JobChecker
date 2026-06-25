"""Pydantic models for profile extraction and building."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ExperienceItem(BaseModel):
    company: str = Field(description="Name of the company or organization")
    role: str = Field(description="Job title or role")
    start_date: Optional[str] = Field(None, description="Start date (e.g. 'Jan 2020')")
    end_date: Optional[str] = Field(None, description="End date (e.g. 'Present' or 'Dec 2022')")
    description: Optional[str] = Field(None, description="Detailed description of responsibilities and achievements")


class EducationItem(BaseModel):
    institution: str = Field(description="Name of the university, college, or school")
    degree: str = Field(description="Degree obtained (e.g. 'B.S. Computer Science')")
    field: Optional[str] = Field(None, description="Field of study or major")
    graduation_year: Optional[str] = Field(None, description="Year of graduation")


class CertificationItem(BaseModel):
    name: str = Field(description="Name of the certification")
    issuer: Optional[str] = Field(None, description="Organization that issued the certification")
    year: Optional[str] = Field(None, description="Year obtained")


class ProjectItem(BaseModel):
    name: str = Field(description="Name of the project")
    description: Optional[str] = Field(None, description="Description of the project and technologies used")
    url: Optional[str] = Field(None, description="Link to the project (e.g. GitHub repo)")


class PublicationItem(BaseModel):
    title: str = Field(description="Title of the publication or paper")
    url: Optional[str] = Field(None, description="Link to the publication")
    year: Optional[str] = Field(None, description="Year of publication")


class SocialLinkItem(BaseModel):
    platform: str = Field(description="Name of the platform (e.g. 'Twitter', 'Personal Blog')")
    url: str = Field(description="URL to the profile")


class ExtractedProfile(BaseModel):
    """Normalized schema for profile data extracted from documents or chat."""
    name: Optional[str] = Field(None, description="Full name of the user")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    github_url: Optional[str] = Field(None, description="GitHub profile URL")
    portfolio_url: Optional[str] = Field(None, description="Personal website or portfolio URL")
    
    target_roles: List[str] = Field(default_factory=list, description="Desired job titles")
    target_locations: List[str] = Field(default_factory=list, description="Desired work locations")
    preferred_industries: List[str] = Field(default_factory=list, description="Preferred industries")
    skills: List[str] = Field(default_factory=list, description="Technical and soft skills")
    
    experience: List[ExperienceItem] = Field(default_factory=list, description="Work experience history")
    education: List[EducationItem] = Field(default_factory=list, description="Educational background")
    certifications: List[CertificationItem] = Field(default_factory=list, description="Certifications obtained")
    projects: List[ProjectItem] = Field(default_factory=list, description="Personal or professional projects")
    publications: List[PublicationItem] = Field(default_factory=list, description="Published papers or articles")
    awards: List[str] = Field(default_factory=list, description="Awards and honors received")
    languages: List[str] = Field(default_factory=list, description="Spoken or written languages (human languages, not programming)")
    social_links: List[SocialLinkItem] = Field(default_factory=list, description="Other social or professional links")

