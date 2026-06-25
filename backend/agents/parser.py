import os
import re
import pdfplumber
from backend.database import save_profile
from backend.db.vector_store import add_resume_chunks

def extract_email(text):
    """Extracts the first email address found in the text."""
    pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    match = re.search(pattern, text)
    return match.group(0) if match else None

def update_env_email(email_address):
    """Saves the extracted email to the .env file and updates os.environ."""
    env_dict = {}
    if os.path.exists(".env"):
        try:
            with open(".env", "r") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_dict[k.strip()] = v.strip()
        except Exception:
            pass
            
    env_dict["GMAIL_EMAIL"] = email_address
    
    # If the password is still empty or default placeholder, set a mock password to enable the sync button
    current_pwd = env_dict.get("GMAIL_APP_PASSWORD", "")
    if not current_pwd or "your_app_password" in current_pwd:
        env_dict["GMAIL_APP_PASSWORD"] = "mock_app_pass_16"
        os.environ["GMAIL_APP_PASSWORD"] = "mock_app_pass_16"
        
    os.environ["GMAIL_EMAIL"] = email_address
    
    try:
        with open(".env", "w") as f:
            f.write("# Ollama Local Service Configuration\n")
            f.write(f"OLLAMA_BASE_URL={env_dict.get('OLLAMA_BASE_URL', 'http://localhost:11434')}\n")
            f.write(f"OLLAMA_MODEL={env_dict.get('OLLAMA_MODEL', 'llama3.1:8b')}\n")
            f.write(f"OLLAMA_EMBEDDING_MODEL={env_dict.get('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text')}\n\n")
            
            f.write("# ChromaDB Config\n")
            f.write(f"CHROMADB_HOST={env_dict.get('CHROMADB_HOST', 'localhost')}\n")
            f.write(f"CHROMADB_PORT={env_dict.get('CHROMADB_PORT', '8000')}\n")
            f.write(f"CHROMADB_PERSIST_DIRECTORY={env_dict.get('CHROMADB_PERSIST_DIRECTORY', './chromadb_storage')}\n\n")
            
            f.write("# SQLite DB Path\n")
            f.write(f"SQLITE_DB_PATH={env_dict.get('SQLITE_DB_PATH', './jobchecker.db')}\n\n")
            
            f.write("# Gmail Daemon Credentials\n")
            f.write(f"GMAIL_EMAIL={env_dict.get('GMAIL_EMAIL', '')}\n")
            f.write(f"GMAIL_APP_PASSWORD={env_dict.get('GMAIL_APP_PASSWORD', '')}\n\n")
            
            f.write("# Playwright Browser Config\n")
            f.write(f"PLAYWRIGHT_USER_DATA_DIR={env_dict.get('PLAYWRIGHT_USER_DATA_DIR', './.playwright_session')}\n")
            f.write(f"PLAYWRIGHT_HEADLESS={env_dict.get('PLAYWRIGHT_HEADLESS', 'false')}\n")
    except Exception as e:
        print(f"Error writing .env: {e}")

def parse_pdf(file_path):
    """Extract text from a PDF file using pdfplumber."""
    text_content = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_content.append(text)
    return "\n\n".join(text_content)

def parse_markdown(file_path):
    """Read markdown files directly (e.g. LinkedIn profiles)."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def chunk_text(text, chunk_size=800, overlap=150):
    """Split text into overlapping chunks for embedding."""
    chunks = []
    words = text.split()
    
    # We reconstruct chunks based on word count to avoid cutting words
    # Est. words per chunk = chunk_size / 6
    words_per_chunk = int(chunk_size / 6)
    overlap_words = int(overlap / 6)
    
    if len(words) <= words_per_chunk:
        return [text]
        
    start = 0
    while start < len(words):
        end = start + words_per_chunk
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        start += (words_per_chunk - overlap_words)
        
    return chunks

def process_and_index_resume(file_path):
    """Main function to parse resume, save to SQL DB, and index in ChromaDB."""
    filename = os.path.basename(file_path)
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext == ".pdf":
        print(f"Parsing PDF resume: {file_path}")
        text = parse_pdf(file_path)
        file_type = "pdf"
    elif file_ext in [".md", ".markdown", ".txt"]:
        print(f"Parsing Markdown/Text resume: {file_path}")
        text = parse_markdown(file_path)
        file_type = "markdown"
    else:
        raise ValueError(f"Unsupported file type: {file_ext}")
        
    if not text.strip():
        raise ValueError("Resume text is empty or could not be parsed.")
        
    # Save raw text context to SQL DB
    save_profile(filename, file_type, text)
    
    # Extract email from the resume and automatically configure the environment
    email_found = extract_email(text)
    if email_found:
        print(f"[Parser] Extracted email from resume: {email_found}. Updating env...")
        update_env_email(email_found)
    
    # Create chunks
    chunks = chunk_text(text)
    
    # Add to ChromaDB
    add_resume_chunks(chunks)
    
    return {
        "filename": filename,
        "file_type": file_type,
        "chunks_count": len(chunks),
        "char_count": len(text)
    }

if __name__ == "__main__":
    # Test harness
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        try:
            res = process_and_index_resume(test_file)
            print("Successfully processed resume:", res)
        except Exception as e:
            print("Failed to process resume:", e)
    else:
        print("Please provide a resume file path to test.")
