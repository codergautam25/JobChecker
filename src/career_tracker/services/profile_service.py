"""Service for managing user profile and CV uploads."""

import shutil
import traceback
import uuid
from typing import Tuple, Any
import re

from career_tracker.config import get_settings
from career_tracker.db.repositories.user_profile_repo import UserProfileRepository
from career_tracker.graph.profile_builder import build_profile_workflow


def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception:
        return ""


def extract_skills_rule_based(text: str) -> list[str]:
    if not text:
        return []
        
    extracted = []
    text_lower = text.lower()
    
    # List of skills to match
    skills_to_match = [
        "python", "javascript", "typescript", "java", "flask", "django", "fastapi", 
        "spring boot", "spring", "kafka", "aws", "new relic", "sql server", "mysql", 
        "postgresql", "postgres", "sqlite", "mongodb", "redis", "elasticsearch", 
        "cassandra", "dynamodb", "docker", "kubernetes", "k8s", "terraform", 
        "ansible", "jenkins", "git", "github", "gitlab", "ci/cd", "microservices", 
        "rest api", "restful api", "restful apis", "graphql", "grpc", "rabbitmq", 
        "opentelemetry", "datadog", "prometheus", "grafana", "secrets manager", 
        "ec2", "emr", "s3", "rds", "lambda", "multithreading", "pyspark", "spark", 
        "hadoop", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", 
        "machine learning", "deep learning", "nlp", "html", "css", "react", 
        "angular", "vue", "next.js", "nextjs", "node.js", "nodejs"
    ]
    
    # We map some variations to a standardized display name
    display_names = {
        "postgres": "PostgreSQL",
        "postgresql": "PostgreSQL",
        "sqlite": "SQLite",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "elasticsearch": "Elasticsearch",
        "cassandra": "Cassandra",
        "dynamodb": "DynamoDB",
        "mysql": "MySQL",
        "sql server": "SQL Server",
        "aws": "AWS",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "k8s": "Kubernetes",
        "terraform": "Terraform",
        "ansible": "Ansible",
        "jenkins": "Jenkins",
        "git": "Git",
        "github": "GitHub",
        "gitlab": "GitLab",
        "ci/cd": "CI/CD",
        "microservices": "Microservices",
        "rest api": "REST APIs",
        "restful api": "REST APIs",
        "restful apis": "REST APIs",
        "graphql": "GraphQL",
        "grpc": "gRPC",
        "rabbitmq": "RabbitMQ",
        "opentelemetry": "OpenTelemetry",
        "datadog": "DataDog",
        "prometheus": "Prometheus",
        "grafana": "Grafana",
        "secrets manager": "AWS Secrets Manager",
        "ec2": "AWS EC2",
        "emr": "AWS EMR",
        "s3": "AWS S3",
        "rds": "AWS RDS",
        "lambda": "AWS Lambda",
        "multithreading": "Multithreading",
        "pyspark": "PySpark",
        "spark": "Apache Spark",
        "hadoop": "Hadoop",
        "pandas": "Pandas",
        "numpy": "NumPy",
        "scikit-learn": "Scikit-Learn",
        "tensorflow": "TensorFlow",
        "pytorch": "PyTorch",
        "machine learning": "Machine Learning",
        "deep learning": "Deep Learning",
        "nlp": "NLP",
        "html": "HTML",
        "css": "CSS",
        "react": "React",
        "angular": "Angular",
        "vue": "Vue.js",
        "next.js": "Next.js",
        "nextjs": "Next.js",
        "node.js": "Node.js",
        "nodejs": "Node.js",
        "python": "Python",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "java": "Java",
        "flask": "Flask",
        "django": "Django",
        "fastapi": "FastAPI",
        "spring boot": "Spring Boot",
        "spring": "Spring",
        "kafka": "Apache Kafka",
        "new relic": "New Relic"
    }
    
    for skill in skills_to_match:
        pattern = rf"\b{re.escape(skill)}\b"
        if skill in ["next.js", "node.js"]:
            pattern = rf"(?:^|\s|\b){re.escape(skill)}(?:\s|\b|$)"
            
        if re.search(pattern, text_lower):
            display = display_names.get(skill, skill.title())
            if display not in extracted:
                extracted.append(display)
                
    return extracted


def run_llm_extraction_background(filepath: str):
    try:
        wf = build_profile_workflow()
        state = {
            'file_path': filepath,
            'raw_text': None,
            'extracted_profile': None,
            'status': '',
            'error': None
        }
        wf.invoke(state)
    except Exception as err:
        import structlog
        structlog.get_logger(__name__).error("background_cv_extraction.failed", error=str(err))


def handle_profile_upload(filepath: str) -> Tuple[str, str, str]:
    """
    Handle the uploading and parsing of a user's CV to extract profile data.
    
    Args:
        filepath: Path to the uploaded CV file.
        
    Returns:
        Tuple of (profile_html, status_message, file_html).
    """
    if not filepath:
        return ("", 'No file uploaded.', "")
        
    try:
        wf = build_profile_workflow()
        state = {'file_path': filepath, 'raw_text': None, 'extracted_profile': None, 'status': '', 'error': None}
        final_state = wf.invoke(state)
        
        if final_state.get('error'):
            return ("", f"Error: {final_state['error']}", "")
            
        return ("", 'Profile updated successfully from document!', "")
    except Exception as e:
        return ("", f'Error parsing document: {e}\n{traceback.format_exc()}', "")


def handle_cv_upload(filepath: str, background_tasks: Any = None) -> dict:
    """
    Save the uploaded PDF file as my_cv.pdf inside the resumes directory,
    extract technical skills immediately using rule-based parsing,
    and trigger full LLM profile extraction in the background.
    """
    if not filepath:
        return {'status': 'error', 'message': 'No file uploaded.', 'extracted_skills': []}
    try:
        settings = get_settings()
        resumes_dir = settings.resolve_path(settings.resumes_dir)
        resumes_dir.mkdir(parents=True, exist_ok=True)
        dest_path = resumes_dir / 'my_cv.pdf'
        shutil.copy(filepath, dest_path)
        
        # Extract text from the PDF
        text = extract_text_from_pdf(str(dest_path))
        
        # Immediate rule-based technical skill extraction
        extracted_skills = extract_skills_rule_based(text)
        
        # ALSO trigger full profile details extraction (name, experience, etc.) in the background
        if background_tasks:
            background_tasks.add_task(run_llm_extraction_background, str(dest_path))
            
        return {
            'status': 'success',
            'message': "CV successfully uploaded and saved as 'my_cv.pdf'!",
            'extracted_skills': extracted_skills
        }
    except Exception as e:
        return {'status': 'error', 'message': f'Error saving CV: {e}', 'extracted_skills': []}


def load_cv_status() -> str:
    """
    Check if the CV PDF exists and return its status text.
    
    Returns:
        String representing the CV status and size.
    """
    try:
        settings = get_settings()
        resumes_dir = settings.resolve_path(settings.resumes_dir)
        cv_path = resumes_dir / 'my_cv.pdf'
        if cv_path.exists():
            size_kb = cv_path.stat().st_size / 1024
            return f'Active CV: my_cv.pdf ({size_kb:.1f} KB)'
        return 'No CV uploaded yet.'
    except Exception as e:
        return f'Error checking CV status: {e}'


def save_profile(name: str, email: str, phone: str, linkedin: str, github: str, portfolio: str, skills_str: str, roles_str: str) -> str:
    """
    Save the user profile data to the database.
    """
    try:
        repo = UserProfileRepository()
        existing = repo.get_default()
        
        skills = [s.strip() for s in skills_str.split(',') if s.strip()]
        roles = [r.strip() for r in roles_str.split(',') if r.strip()]
        
        profile_data = {
            'name': name.strip(),
            'email': email.strip(),
            'phone': phone.strip(),
            'linkedin_url': linkedin.strip(),
            'github_url': github.strip(),
            'portfolio_url': portfolio.strip(),
            'skills': skills,
            'target_roles': roles
        }
        
        if existing:
            repo.update(existing['id'], profile_data)
            return f'Profile updated for {name}. Drafts will now use your real name and contact info.'
        else:
            profile_data['id'] = str(uuid.uuid4())
            repo.create(profile_data)
            return f'Profile created for {name}. Drafts will now use your real name and contact info.'
    except Exception as e:
        return f'Error saving profile: {e}'
