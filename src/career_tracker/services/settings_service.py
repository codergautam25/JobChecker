"""Service for managing application settings and environment variables."""

import shutil
from pathlib import Path
from typing import Dict, Tuple

from career_tracker.db.repositories.user_profile_repo import UserProfileRepository

ROOT = Path.cwd()


def load_settings() -> Tuple[str, str, str, str, str, str]:
    """
    Read current .env values.
    
    Returns:
        Tuple containing API Key, Base URL, Model, Poll Interval, Cache TTL, and a status message.
    """
    env_path = ROOT / '.env'
    if not env_path.exists():
        return ('', '', '', '', '', 'No .env file found. Copy .env.example to .env first.')
        
    values: Dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            values[k.strip()] = v.strip()
            
    return (
        values.get('OPENAI_API_KEY', ''),
        values.get('OPENAI_API_BASE', 'https://api.openai.com/v1'),
        values.get('LLM_MODEL', 'gpt-4o-mini'),
        values.get('EMAIL_POLL_INTERVAL_SECONDS', '300'),
        values.get('UI_CACHE_TTL_SECONDS', '60'),
        'Settings loaded.'
    )


def save_settings(api_key: str, api_base: str, model: str, poll_interval: str, cache_ttl: str = '60') -> str:
    """
    Write updated settings to .env file.
    
    Args:
        api_key: OpenAI API key.
        api_base: OpenAI Base URL.
        model: LLM model name.
        poll_interval: Email poll interval in seconds.
        cache_ttl: UI cache TTL in seconds.
        
    Returns:
        A status message string.
    """
    env_path = ROOT / '.env'
    if not env_path.exists():
        example = ROOT / '.env.example'
        if example.exists():
            shutil.copy(example, env_path)
        else:
            env_path.write_text('')
            
    lines = env_path.read_text().splitlines()
    updates = {
        'OPENAI_API_KEY': api_key,
        'OPENAI_API_BASE': api_base,
        'LLM_MODEL': model,
        'EMAIL_POLL_INTERVAL_SECONDS': poll_interval,
        'UI_CACHE_TTL_SECONDS': cache_ttl
    }
    
    new_lines = []
    updated_keys = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            k, _, _ = stripped.partition('=')
            k = k.strip()
            if k in updates:
                new_lines.append(f'{k}={updates[k]}')
                updated_keys.add(k)
                continue
        new_lines.append(line)
        
    for k, v in updates.items():
        if k not in updated_keys:
            new_lines.append(f'{k}={v}')
            
    env_path.write_text('\n'.join(new_lines) + '\n')
    
    # Update current process environment variables and clear config cache
    import os
    from career_tracker.config import get_settings
    from career_tracker.llm.client import get_llm
    for k, v in updates.items():
        os.environ[k] = str(v)
    get_settings.cache_clear()
    get_llm.cache_clear()
    
    return 'Settings saved to .env'


def check_setup() -> str:
    """
    Check which setup steps are complete for the system configuration.
    
    Returns:
        A formatted string detailing the status of various configuration requirements.
    """
    lines = []
    env_path = ROOT / '.env'
    creds_path = ROOT / 'data' / 'credentials.json'
    token_path = ROOT / 'data' / 'token.json'
    db_path = ROOT / 'data' / 'career_tracker.db'
    chroma_path = ROOT / 'data' / 'chroma'
    
    lines.append(f"{'[OK]' if env_path.exists() else '[!!]'} .env file: {'found' if env_path.exists() else 'MISSING'}")
    lines.append(f"{'[OK]' if creds_path.exists() else '[!!]'} Gmail credentials: {'found' if creds_path.exists() else 'MISSING'}")
    lines.append(f"{'[OK]' if token_path.exists() else '[ ]'} Gmail token: {'found (authenticated)' if token_path.exists() else 'not yet'}")
    lines.append(f"{'[OK]' if db_path.exists() else '[!!]'} Database: {'found' if db_path.exists() else 'MISSING'}")
    lines.append(f"{'[OK]' if chroma_path.exists() else '[!!]'} ChromaDB: {'found' if chroma_path.exists() else 'MISSING'}")
    
    api_key = ''
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith('OPENAI_API_KEY='):
                api_key = line.split('=', 1)[1].strip()
                
    is_key_set = bool(api_key and api_key != 'your-api-key-here')
    lines.append(f"{'[OK]' if is_key_set else '[!!]'} OpenAI API Key: {'configured' if is_key_set else 'NOT SET'}")
    
    try:
        profile = UserProfileRepository().get_default()
        has_name = bool(profile and profile.get('name'))
        lines.append(f"{'[OK]' if has_name else '[!!]'} User profile: {'configured' if has_name else 'NOT SET — go to Settings > My Profile'}")
    except Exception:
        lines.append('[!!] User profile: could not check')
        
    return '\n'.join(lines)
