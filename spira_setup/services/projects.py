"""
spira_setup.services.projects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create and look up Spira projects (products).

Note: Programs cannot be created via the REST API — they must be created
manually in the Spira admin UI first.  This module can look up a program by
name so the runner can verify it exists before proceeding.
"""

import logging
from typing import Optional

from spira_setup.client import SpiraClient

logger = logging.getLogger(__name__)


def get_all_projects(client: SpiraClient) -> list:
    """Return all projects the authenticated user can see."""
    return client.get("projects") or []


def get_project_by_name(client: SpiraClient, name: str) -> Optional[dict]:
    """Return the first project whose name matches *name*, or ``None``."""
    for project in get_all_projects(client):
        if project.get("Name", "").strip().lower() == name.strip().lower():
            return project
    return None


def get_all_programs(client: SpiraClient) -> list:
    """Return all programs the authenticated user can see."""
    return client.get("programs") or []


def get_program_by_name(client: SpiraClient, name: str) -> Optional[dict]:
    """Return the first program whose name matches *name*, or ``None``."""
    for program in get_all_programs(client):
        if program.get("Name", "").strip().lower() == name.strip().lower():
            return program
    return None


def create_project(
    client: SpiraClient,
    name: str,
    description: str = "",
    program_id: Optional[int] = None,
    existing_project_id: Optional[int] = None,
) -> dict:
    """
    Create a new Spira project (product).

    If a project with *name* already exists it is returned as-is (idempotent).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    name:
        Display name for the new project.
    description:
        Optional project description.
    program_id:
        If provided, the project will be associated with this program.
    existing_project_id:
        If provided, the new project will be cloned from this project's
        template (Spira ``?existing_project_id=`` query param).

    Returns
    -------
    dict
        The created (or pre-existing) project object from the API.
    """
    existing = get_project_by_name(client, name)
    if existing:
        logger.info("Project '%s' already exists (id=%s) — skipping.", name, existing["ProjectId"])
        return existing

    body: dict = {"Name": name}
    if description:
        body["Description"] = description
    if program_id is not None:
        body["ProjectGroupId"] = program_id

    params = {}
    if existing_project_id is not None:
        params["existing_project_id"] = existing_project_id

    project = client.post("projects", body, params=params or None)
    logger.info("Created project '%s' (id=%s).", name, project["ProjectId"])
    return project
