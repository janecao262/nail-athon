import os
from datetime import date
from jira import JIRA, JIRAError
from langchain_core.tools import tool

_url: str = os.getenv("JIRA_URL", "")
_email: str = os.getenv("JIRA_EMAIL", "")
_token: str = os.getenv("JIRA_API_TOKEN", "")
_project: str = os.getenv("JIRA_PROJECT_KEY", "")
_client: JIRA | None = None


def set_config(url: str = "", email: str = "", token: str = "", project: str = "") -> None:
    """Update Jira connection config for the current session and reset the client."""
    global _url, _email, _token, _project, _client
    if url:
        _url = url
    if email:
        _email = email
    if token:
        _token = token
    if project:
        _project = project
    _client = None


def _get_project() -> str:
    """Return the active project key, falling back to the env var if not set via set_config."""
    return _project or os.getenv("JIRA_PROJECT_KEY", "")


def _scoped_jql(jql: str) -> str:
    """Prepend project filter to a JQL query if not already present."""
    project = _get_project()
    if project and "project" not in jql.lower():
        return f"project = {project} AND ({jql})" if jql else f"project = {project}"
    return jql or (f"project = {project}" if project else jql)


def _jira() -> JIRA:
    global _client
    if _client is None:
        if not all([_url, _email, _token]):
            raise ValueError(
                "Jira credentials not configured. "
                "Include 'jira_config' in your first request with: url, email, token, project."
            )
        _client = JIRA(server=_url, basic_auth=(_email, _token))
    return _client


def _fmt_issue(issue) -> str:
    f = issue.fields
    sp = getattr(f, "story_points", None) or getattr(f, "customfield_10016", None)
    due = getattr(f, "duedate", None)
    assignee = f.assignee.displayName if f.assignee else "Unassigned"
    return (
        f"{issue.key} | {f.summary}\n"
        f"  Status: {f.status.name}  Priority: {f.priority.name if f.priority else 'N/A'}\n"
        f"  Assignee: {assignee}  Story Points: {sp or 'N/A'}  Due: {due or 'N/A'}\n"
        f"  Description: {(f.description or '').strip()[:400] or 'N/A'}"
    )


@tool
def get_issue(issue_key: str) -> str:
    """Get full details of a Jira issue by its key (e.g. PROJ-123).
    Returns summary, description, status, assignee, priority, story points, and due date."""
    try:
        return _fmt_issue(_jira().issue(issue_key))
    except Exception as e:
        return f"Error fetching {issue_key}: {e}"


@tool
def search_issues(jql: str, max_results: int = 20) -> str:
    """Search Jira issues using JQL (Jira Query Language).
    Use this for any query not covered by the other tools.
    Example JQL: 'project = PROJ AND status = \"In Progress\" ORDER BY priority DESC'"""
    try:
        issues = _jira().search_issues(_scoped_jql(jql), maxResults=max_results)
        if not issues:
            return "No issues found."
        lines = [f"Found {len(issues)} issue(s):\n"]
        for i in issues:
            f = i.fields
            due = getattr(f, "duedate", None)
            assignee = f.assignee.displayName if f.assignee else "Unassigned"
            lines.append(f"  {i.key} | {f.summary} | {f.status.name} | {assignee} | Due: {due or 'N/A'}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching issues: {e}"


@tool
def list_project_issues(
    status: str = "",
    assignee: str = "",
    priority: str = "",
    max_results: int = 25,
) -> str:
    """List issues in the configured Jira project with optional filters.
    Args:
        status: Filter by status name, e.g. 'To Do', 'In Progress', 'Done'. Leave empty for all.
        assignee: Filter by assignee display name or account ID. Leave empty for all.
        priority: Filter by priority name, e.g. 'High', 'Medium', 'Low'. Leave empty for all.
        max_results: Maximum number of issues to return (default 25).
    """
    clauses = [f"project = {_get_project()}"]
    if status:
        clauses.append(f'status = "{status}"')
    if assignee:
        clauses.append(f'assignee = "{assignee}"')
    if priority:
        clauses.append(f'priority = "{priority}"')
    jql = " AND ".join(clauses) + " ORDER BY priority ASC, duedate ASC"
    try:
        issues = _jira().search_issues(jql, maxResults=max_results)
        if not issues:
            return "No issues found matching the filters."
        lines = [f"Found {len(issues)} issue(s) in {_get_project()}:\n"]
        for i in issues:
            f = i.fields
            due = getattr(f, "duedate", None)
            assignee_name = f.assignee.displayName if f.assignee else "Unassigned"
            lines.append(f"  {i.key} | {f.summary} | {f.status.name} | {assignee_name} | Due: {due or 'N/A'}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing issues: {e}"


@tool
def count_issues(jql: str = "") -> str:
    """Count the number of Jira issues matching a JQL query.
    If jql is empty, counts all issues in the configured project.
    Example: jql='project = PROJ AND status != Done AND priority = High'"""
    try:
        scoped = _scoped_jql(jql)
        result = _jira().search_issues(scoped, maxResults=0)
        return f"Total issues matching '{scoped}': {result.total}"
    except Exception as e:
        return f"Error counting issues: {e}"


@tool
def get_issues_due_before(target_date: str) -> str:
    """Get all unresolved issues in the project with a due date before the given date.
    Args:
        target_date: Date in YYYY-MM-DD format (e.g. '2026-07-01').
    """
    jql = (
        f"project = {_get_project()} "
        f"AND duedate < '{target_date}' "
        f"AND statusCategory != Done "
        f"ORDER BY duedate ASC"
    )
    try:
        issues = _jira().search_issues(jql, maxResults=50)
        if not issues:
            return f"No unresolved issues due before {target_date}."
        lines = [f"{len(issues)} unresolved issue(s) due before {target_date}:\n"]
        for i in issues:
            f = i.fields
            due = getattr(f, "duedate", None)
            assignee = f.assignee.displayName if f.assignee else "Unassigned"
            lines.append(f"  {i.key} | {f.summary} | {f.status.name} | {assignee} | Due: {due}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching issues due before {target_date}: {e}"


@tool
def get_overdue_issues() -> str:
    """Get all issues in the project that are past their due date and not yet Done."""
    today = date.today().isoformat()
    jql = (
        f"project = {_get_project()} "
        f"AND duedate < '{today}' "
        f"AND statusCategory != Done "
        f"ORDER BY duedate ASC"
    )
    try:
        issues = _jira().search_issues(jql, maxResults=50)
        if not issues:
            return "No overdue issues. Everything is on track!"
        lines = [f"{len(issues)} overdue issue(s):\n"]
        for i in issues:
            f = i.fields
            due = getattr(f, "duedate", None)
            assignee = f.assignee.displayName if f.assignee else "Unassigned"
            lines.append(f"  {i.key} | {f.summary} | {f.status.name} | {assignee} | Due: {due}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching overdue issues: {e}"


@tool
def get_sprint_issues() -> str:
    """Get all issues in the currently active sprint for the configured project."""
    jql = (
        f"project = {_get_project()} "
        f"AND sprint in openSprints() "
        f"ORDER BY status ASC, priority ASC"
    )
    try:
        issues = _jira().search_issues(jql, maxResults=100)
        if not issues:
            return "No active sprint found, or the sprint has no issues."
        lines = [f"{len(issues)} issue(s) in the active sprint:\n"]
        for i in issues:
            f = i.fields
            due = getattr(f, "duedate", None)
            assignee = f.assignee.displayName if f.assignee else "Unassigned"
            sp = getattr(f, "story_points", None) or getattr(f, "customfield_10016", None)
            lines.append(
                f"  {i.key} | {f.summary} | {f.status.name} | {assignee} | SP: {sp or '?'} | Due: {due or 'N/A'}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching sprint issues: {e}"


@tool
def get_workload_summary() -> str:
    """Get a summary of open and in-progress task counts per assignee in the project.
    Useful for understanding workload distribution across the team."""
    jql = f"project = {_get_project()} AND statusCategory != Done AND assignee is not EMPTY"
    try:
        issues = _jira().search_issues(jql, maxResults=200)
        if not issues:
            return "No open issues with assignees found."
        counts: dict[str, int] = {}
        for i in issues:
            name = i.fields.assignee.displayName if i.fields.assignee else "Unassigned"
            counts[name] = counts.get(name, 0) + 1
        lines = ["Workload summary (open + in-progress tasks per person):\n"]
        for name, count in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {name}: {count} task(s)")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching workload summary: {e}"


ALL_TOOLS = [
    get_issue,
    search_issues,
    list_project_issues,
    count_issues,
    get_issues_due_before,
    get_overdue_issues,
    get_sprint_issues,
    get_workload_summary,
]
