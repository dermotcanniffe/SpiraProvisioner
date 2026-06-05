"""
spira_setup.services.risks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create and look up risks within a Spira project.
"""

import logging
from typing import Any, Dict, List, Optional

from spira_setup.client import SpiraClient

logger = logging.getLogger(__name__)


def get_risks(client: SpiraClient, project_id: int) -> List[Dict[str, Any]]:
    """Return all risks for *project_id*."""
    return client.post(
        f"projects/{project_id}/risks",
        body=[],
        params={
            "starting_row": 1,
            "number_of_rows": 10000,
            "sort_field": "RiskId",
            "sort_direction": "ASC",
        },
    ) or []


def get_risk_by_name(
    client: SpiraClient, project_id: int, name: str
) -> Optional[Dict[str, Any]]:
    """
    Return the first risk in *project_id* whose name matches, or ``None``.

    The comparison is case-insensitive and strips leading/trailing whitespace.
    """
    for risk in get_risks(client, project_id):
        if risk.get("Name", "").strip().lower() == name.strip().lower():
            return risk
    return None


def _get_default_risk_type_id(client: SpiraClient, project_id: int) -> int:
    """
    Look up the default risk type ID for the template associated with
    *project_id*.  Falls back to the first available type if no default is set.

    Raises
    ------
    ValueError
        If no risk types are configured for the project's template.
    """
    project = client.get(f"projects/{project_id}")
    template_id = project.get("ProjectTemplateId")
    types = client.get(f"project-templates/{template_id}/risks/types") or []
    for t in types:
        if t.get("IsDefault"):
            return t["RiskTypeId"]
    if types:
        return types[0]["RiskTypeId"]
    raise ValueError(f"No risk types found for project {project_id}")


def create_risk(
    client: SpiraClient,
    project_id: int,
    name: str,
    description: str = "",
    probability: Optional[int] = None,
    impact: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a risk in *project_id*.

    If a risk with *name* already exists it is returned as-is (idempotent).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    name:
        Display name for the risk.
    description:
        Optional description of the risk.
    probability:
        Optional probability rating (1-5).  Maps directly to
        ``RiskProbabilityId`` in the Spira API.
    impact:
        Optional impact rating (1-5).  Maps directly to
        ``RiskImpactId`` in the Spira API.

    Returns
    -------
    dict
        The created (or pre-existing) risk object from the API.
    """
    existing = get_risk_by_name(client, project_id, name)
    if existing:
        logger.info(
            "Risk '%s' already exists in project %s (id=%s) — skipping.",
            name,
            project_id,
            existing["RiskId"],
        )
        return existing

    risk_type_id = _get_default_risk_type_id(client, project_id)

    body: Dict[str, Any] = {
        "Name": name,
        "Description": description,
        "RiskTypeId": risk_type_id,
    }

    if probability is not None:
        body["RiskProbabilityId"] = probability

    if impact is not None:
        body["RiskImpactId"] = impact

    risk = client.post(f"projects/{project_id}/risks", body)
    logger.info(
        "Created risk '%s' in project %s (id=%s).",
        name,
        project_id,
        risk["RiskId"],
    )
    return risk
