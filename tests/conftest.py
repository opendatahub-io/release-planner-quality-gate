"""Shared test fixtures — jira-emulator server for integration tests."""
import base64
import json
import os
import socket
import threading
import time
import urllib.request

import pytest


SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


def _find_free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _jira_request(base_url, method, path, body=None):
    """Make a request to the jira-emulator."""
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body is not None else None
    creds = base64.b64encode(b"admin:admin").decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        if resp.status == 204:
            return None
        body_bytes = resp.read()
        return json.loads(body_bytes) if body_bytes else None


@pytest.fixture(scope="session")
def jira_emu():
    """Start a jira-emulator server for the test session."""
    port = _find_free_port()

    att_dir = __import__("tempfile").mkdtemp(prefix="jira-emu-attachments-")
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
    os.environ["AUTH_MODE"] = "none"
    os.environ["SEED_DATA"] = "true"
    os.environ["ATTACHMENT_DIR"] = att_dir
    os.environ["BASE_URL"] = f"http://127.0.0.1:{port}"

    from jira_emulator.config import get_settings
    get_settings.cache_clear()
    from jira_emulator.database import reset_engine
    reset_engine()
    from jira_emulator.app import create_app
    import uvicorn

    app = create_app()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{base_url}/")
            break
        except Exception:
            time.sleep(0.05)

    yield base_url
    server.should_exit = True


@pytest.fixture
def jira(jira_emu):
    """Per-test fixture: resets emulator state and provides helpers."""
    req = urllib.request.Request(
        f"{jira_emu}/api/admin/reset", method="POST", data=b"")
    urllib.request.urlopen(req)

    class JiraHelper:
        url = jira_emu

        @staticmethod
        def create(key, summary, description="", labels=None,
                   priority=None, custom_fields=None):
            """Import an issue with a specific key."""
            issue = {
                "key": key,
                "summary": summary,
                "project": key.split("-")[0],
                "issue_type": "Feature",
                "description": description,
            }
            if labels:
                issue["labels"] = labels
            if priority:
                issue["priority"] = priority
            if custom_fields:
                issue.update(custom_fields)
            _jira_request(jira_emu, "POST", "/api/admin/import",
                          {"issues": [issue]})

        @staticmethod
        def get(key):
            """GET an issue, return parsed JSON."""
            return _jira_request(jira_emu, "GET",
                                 f"/rest/api/3/issue/{key}")

        @staticmethod
        def search(jql, fields="key,summary,labels,priority"):
            """JQL search, return list of issues."""
            from urllib.parse import quote
            path = (f"/rest/api/3/search/jql"
                    f"?jql={quote(jql, safe='')}&fields={fields}")
            data = _jira_request(jira_emu, "GET", path)
            return data.get("issues", [])

        @staticmethod
        def request(method, path, body=None):
            """Make an arbitrary API request to the emulator."""
            return _jira_request(jira_emu, method, path, body)

    return JiraHelper()


@pytest.fixture
def art_dir(tmp_path):
    """Create artifacts directory in a temp dir and chdir there."""
    (tmp_path / "artifacts").mkdir(parents=True)
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(old_cwd)


@pytest.fixture
def scripts_dir():
    """Return the path to the scripts/ directory."""
    return os.path.abspath(SCRIPTS_DIR)


@pytest.fixture
def config_dir():
    """Return the path to the config/ directory."""
    return os.path.abspath(CONFIG_DIR)
