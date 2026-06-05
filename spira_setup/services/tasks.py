"""
spira_setup.services.tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create and look up tasks within a Spira project.
"""

import logging
from typing import Any, Dict, List, Optional

from spira_setup.client import SpiraClient

logger = logging.getLogger(__name__)


def get_tasks(client: SpiraClient, project_id: int) -> List[Dict[str, Any]]:
    """Return all tasks for *project_id*."""
    return client.post(
        f"projects/{project_id}/tasks",
        body=[],
        params={
            "starting_row": 1,
            "number_of_rows": 10000,
            "sort_field": "TaskId",
            "sort_direction": "ASC",
        },
    ) or []


def get_task_by_name(
    client: SpiraClient, project_id: int, name: str
) -> Optional[Dict[str, Any]]:
    """
    Return the first task in *project_id* whose name matches, or ``None``.

    The comparison is case-insensitive and strips leading/trailing whitespace.
    """
    for task in get_tasks(client, project_id):
        if task.get("Name", "").strip().lower() == name.strip().lower():
            return task
    return None


def _get_default_task_type_id(client: SpiraClient, project_id: int) -> int:
    """
    Look up the default task type ID for the template associated with
    *project_id*.  Falls back to the first available type if no default is set.

    Raises
    ------
    ValueError
        If no task types are configured for the project's template.
    """
    project = client.get(f"projects/{project_id}")
    template_id = project.get("ProjectTemplateId")
    types = client.get(f"project-templates/{template_id}/tasks/types") or []
    for t in types:
        if t.get("IsDefault"):
            return t["TaskTypeId"]
    if types:
        return types[0]["TaskTypeId"]
    raise ValueError(f"No task types found for project {project_id}")


def _resolve_task_type_id(
    client: SpiraClient, project_id: int, type_name: str
) -> int:
    """
    Resolve a task type display name to its numeric ``TaskTypeId``.

    The lookup is case-insensitive.  If no matching type is found, falls back
    to the default task type for the project's template.

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    type_name:
        Display name of the desired task type (e.g. ``"Development"``).

    Returns
    -------
    int
        The resolved ``TaskTypeId``.
    """
    project = client.get(f"projects/{project_id}")
    template_id = project.get("ProjectTemplateId")
    types = client.get(f"project-templates/{template_id}/tasks/types") or []

    for t in types:
        if t.get("Name", "").strip().lower() == type_name.strip().lower():
            return t["TaskTypeId"]

    logger.warning(
        "Task type '%s' not found for project %s — using default type.",
        type_name,
        project_id,
    )
    return _get_default_task_type_id(client, project_id)


def create_task(
    client: SpiraClient,
    project_id: int,
    name: str,
    description: str = "",
    task_type_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a task in *project_id*.

    If a task with *name* already exists it is returned as-is (idempotent).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    name:
        Display name for the task.
    description:
        Optional description of the task.
    task_type_id:
        Optional task type ID.  If not provided the default task type for
        the project's template is used.

    Returns
    -------
    dict
        The created (or pre-existing) task object from the API.
    """
    existing = get_task_by_name(client, project_id, name)
    if existing:
        logger.info(
            "Task '%s' already exists in project %s (id=%s) — skipping.",
            name,
            project_id,
            existing["TaskId"],
        )
        return existing

    if task_type_id is None:
        task_type_id = _get_default_task_type_id(client, project_id)

    body: Dict[str, Any] = {
        "Name": name,
        "Description": description,
        "TaskTypeId": task_type_id,
        "TaskStatusId": 1,  # 1 = Not Started
    }

    task = client.post(f"projects/{project_id}/tasks", body)
    logger.info(
        "Created task '%s' in project %s (id=%s).",
        name,
        project_id,
        task["TaskId"],
    )
    return task
