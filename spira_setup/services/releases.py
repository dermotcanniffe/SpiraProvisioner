"""
spira_setup.services.releases
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create and look up releases (test periods / sprints) within a Spira project.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from spira_setup.client import SpiraClient

logger = logging.getLogger(__name__)

# Default release type IDs in a standard Spira template:
#   1 = Major Release, 2 = Minor Release, 3 = Sprint / Iteration
RELEASE_TYPE_SPRINT = 3


def get_releases(client: SpiraClient, project_id: int) -> list:
    """Return all releases for *project_id*."""
    return client.get(f"projects/{project_id}/releases", params={"active_only": "false"}) or []


def get_release_by_name(
    client: SpiraClient, project_id: int, name: str
) -> Optional[dict]:
    """Return the first release in *project_id* whose name matches, or ``None``."""
    for release in get_releases(client, project_id):
        if release.get("Name", "").strip().lower() == name.strip().lower():
            return release
    return None


def create_release(
    client: SpiraClient,
    project_id: int,
    name: str,
    release_type_id: int = RELEASE_TYPE_SPRINT,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """
    Create a release at the root level of *project_id*.

    If a release with *name* already exists it is returned as-is (idempotent).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    name:
        Display name for the release.
    release_type_id:
        Spira release type.  Defaults to Sprint/Iteration (3).
    start_date:
        ISO 8601 date string.  Defaults to today.
    end_date:
        ISO 8601 date string.  Defaults to 30 days from today.

    Returns
    -------
    dict
        The created (or pre-existing) release object from the API.
    """
    existing = get_release_by_name(client, project_id, name)
    if existing:
        logger.info(
            "Release '%s' already exists in project %s (id=%s) — skipping.",
            name, project_id, existing["ReleaseId"],
        )
        return existing

    today = datetime.utcnow()
    body = {
        "Name": name,
        "ReleaseTypeId": release_type_id,
        "ReleaseStatusId": 1,  # 1 = Planned
        "StartDate": (start_date or today.strftime("%Y-%m-%dT00:00:00.000Z")),
        "EndDate": (
            end_date
            or (today + timedelta(days=30)).strftime("%Y-%m-%dT00:00:00.000Z")
        ),
        "VersionNumber": "1.0",
    }

    release = client.post(f"projects/{project_id}/releases", body)
    logger.info(
        "Created release '%s' in project %s (id=%s).",
        name, project_id, release["ReleaseId"],
    )
    return release
