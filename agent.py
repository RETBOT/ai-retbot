import requests
import json
import re
import os
from datetime import datetime

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "phi3:mini")

sessions = {}


def call_ollama(messages, model=None, stream=False):
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model or MODEL_NAME,
                "messages": messages,
                "stream": stream
            },
            stream=stream,
            timeout=120
        )
        response.raise_for_status()
        return response
    except Exception as e:
        return None


def extract_json(text):
    try:
        match = re.search(r"\{[\s\S]*?\}", text)
        if match:
            return json.loads(match.group(0))
    except:
        pass
    return None


def handle_stream(response, session, messages):
    full_content = ""
    
    for line in response.iter_lines():
        if line:
            try:
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    full_content += content
            except:
                pass
    
    return full_content


def handle_agent(user_input, session_id=None):
    if not isinstance(user_input, str):
        user_input = str(user_input)

    if not session_id:
        session_id = str(datetime.now().timestamp())

    if session_id not in sessions:
        sessions[session_id] = {"history": [], "created_at": str(datetime.now())}

    session = sessions[session_id]
    session["history"].append({"role": "user", "content": user_input})

    history = session["history"][-20:]

    system_prompt = {
        "role": "system",
        "content": """You are a coding assistant. Use tools when needed.

AVAILABLE TOOLS (all return text):
- read_file(path, offset=0, limit=200): Read file content
- write_file(path, content): Write/create file  
- glob(pattern, path=None): Find files by pattern
- grep(pattern, path=None, include="*"): Search text in files
- bash(command): Run shell command
- list_files(path=None): List directory contents
- question(questions): Ask user for choices

When using tools, respond ONLY with valid JSON:
{"tool": "tool_name", "param": "value"}

Rules:
1. Keep responses SHORT and direct
2. Use code blocks for code examples
3. When tool is needed, respond ONLY with JSON
4. If tool fails, explain error and try different approach
5. After tool result, analyze it and respond or call another tool"""
    }

    messages = [system_prompt] + history

    response = call_ollama(messages, stream=True)

    if response is None:
        return {"error": "Ollama not available"}

    full_content = handle_stream(response, session, messages)

    for _ in range(3):
        if '"tool"' in full_content or '"tool":' in full_content:
            data = extract_json(full_content)
            if data and "tool" in data:
                session["history"].append({"role": "assistant", "content": full_content})
                session["history"].append({"role": "tool", "content": f"Tool: {data.get('tool')} called"})
                messages.append({"role": "assistant", "content": full_content})
                messages.append({"role": "tool", "content": "Tool executed"})

                response = call_ollama(messages, stream=True)
                if response:
                    full_content = handle_stream(response, session, messages)
                else:
                    break
            else:
                break
        else:
            break

    session["history"].append({"role": "assistant", "content": full_content})

    return {
        "content": full_content,
        "session_id": session_id
    }
