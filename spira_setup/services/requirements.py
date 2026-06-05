"""
spira_setup.services.requirements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create and look up requirements within a Spira project, including support
for hierarchical parent-child relationships via the indent endpoint.
"""

import logging
from typing import Any, Dict, List, Optional

from spira_setup.client import SpiraClient

logger = logging.getLogger(__name__)


def get_requirements(client: SpiraClient, project_id: int) -> List[Dict[str, Any]]:
    """Return all requirements for *project_id*."""
    return client.get(
        f"projects/{project_id}/requirements",
        params={"starting_row": 1, "number_of_rows": 10000},
    ) or []


def get_requirement_by_name(
    client: SpiraClient,
    project_id: int,
    name: str,
    parent_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Return the first requirement in *project_id* whose name matches at the
    specified hierarchy level, or ``None``.

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    name:
        The requirement name to search for (case-insensitive).
    parent_id:
        If provided, only match requirements whose
        ``IndentLevel`` indicates they are children of this parent.
        If ``None``, matches requirements at any level with the given name.

    Returns
    -------
    Optional[dict]
        The matching requirement object, or ``None`` if not found.
    """
    all_requirements = get_requirements(client, project_id)

    for req in all_requirements:
        if req.get("Name", "").strip().lower() == name.strip().lower():
            # If no parent filter, return first name match
            if parent_id is None:
                return req
            # If parent filter specified, check the requirement's parent
            if req.get("RequirementId") and req.get("IndentLevel"):
                # Spira stores hierarchy via indent levels; we match by
                # checking if the requirement's summary flag and position
                # indicate it belongs under the given parent.
                # A more reliable check: look at the requirement's parent
                # via the indent structure — requirements directly under a
                # parent have that parent's ID in their hierarchy.
                # We use a positional heuristic: the requirement should
                # appear after the parent in the flat list.
                pass
    # Fallback: filter by parent_id if provided
    if parent_id is not None:
        for req in all_requirements:
            if (
                req.get("Name", "").strip().lower() == name.strip().lower()
                and _is_child_of(req, parent_id, all_requirements)
            ):
                return req
    else:
        # Already checked above, return None
        pass

    return None


def _is_child_of(
    requirement: Dict[str, Any],
    parent_id: int,
    all_requirements: List[Dict[str, Any]],
) -> bool:
    """
    Determine if *requirement* is a direct child of the requirement with
    *parent_id* by examining the flat ordered list and indent levels.

    Spira returns requirements in a flat list ordered by their position in
    the hierarchy.  A requirement is a direct child of *parent_id* if:
    1. It appears after the parent in the list.
    2. Its ``IndentLevel`` is exactly one more than the parent's.
    3. No requirement with a lower-or-equal indent level to the parent
       appears between them (which would indicate a different subtree).

    ``IndentLevel`` in the Spira API is a string-based position encoding
    (e.g. ``"AAA"``, ``"AAABBB"``). Each level adds 3 characters. A direct
    child has ``len(indent) == len(parent_indent) + 3``.
    """
    parent_indent = None
    parent_index = None

    for i, req in enumerate(all_requirements):
        if req.get("RequirementId") == parent_id:
            parent_indent = req.get("IndentLevel", "")
            parent_index = i
            break

    if parent_index is None or parent_indent is None:
        return False

    # Determine the expected child indent length
    parent_indent_len = len(str(parent_indent))
    child_indent_len = parent_indent_len + 3

    req_id = requirement.get("RequirementId")
    # Walk from parent+1 forward
    for i in range(parent_index + 1, len(all_requirements)):
        r = all_requirements[i]
        r_indent = str(r.get("IndentLevel", ""))
        if len(r_indent) <= parent_indent_len:
            # We've left the parent's subtree
            break
        if r.get("RequirementId") == req_id and len(r_indent) == child_indent_len:
            return True

    return False


def create_requirement(
    client: SpiraClient,
    project_id: int,
    name: str,
    description: str = "",
    parent_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a requirement in *project_id*, optionally indented under *parent_id*.

    If a requirement with *name* already exists at the same hierarchy level
    it is returned as-is (idempotent).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    name:
        Display name for the requirement.
    description:
        Optional description of the requirement.
    parent_id:
        If provided, the requirement is indented under this parent
        requirement after creation.

    Returns
    -------
    dict
        The created (or pre-existing) requirement object from the API.
    """
    existing = get_requirement_by_name(client, project_id, name, parent_id)
    if existing:
        logger.info(
            "Requirement '%s' already exists in project %s (id=%s) — skipping.",
            name,
            project_id,
            existing["RequirementId"],
        )
        return existing

    body: Dict[str, Any] = {
        "Name": name,
        "Description": description,
    }

    if parent_id is not None:
        # Create directly under the parent using the dedicated endpoint
        requirement = client.post(
            f"projects/{project_id}/requirements/parent/{parent_id}", body
        )
    else:
        requirement = client.post(f"projects/{project_id}/requirements", body)

    logger.info(
        "Created requirement '%s' in project %s (id=%s).",
        name,
        project_id,
        requirement["RequirementId"],
    )

    return requirement


def _indent_requirement(
    client: SpiraClient, project_id: int, requirement_id: int
) -> None:
    """
    Indent a requirement one level deeper using the Spira indent endpoint.

    This moves the requirement to become a child of the requirement
    immediately above it in the hierarchy.
    """
    client.post(
        f"projects/{project_id}/requirements/{requirement_id}/indent"
    )


def create_requirements_recursive(
    client: SpiraClient,
    project_id: int,
    requirements: List[Dict[str, Any]],
    parent_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Recursively create a hierarchy of requirements (depth-first).

    Each requirement definition may contain a ``children`` list of nested
    requirement definitions.  Parents are created before their children to
    ensure valid parent IDs are available for indentation.

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    requirements:
        List of requirement definitions, each with at minimum a ``name``
        key, and optionally ``description`` and ``children``.
    parent_id:
        The parent requirement ID under which to nest these requirements.
        ``None`` for top-level requirements.

    Returns
    -------
    list
        List of all created (or pre-existing) requirement objects.
    """
    created: List[Dict[str, Any]] = []

    for req_def in requirements:
        name = req_def["name"]
        description = req_def.get("description", "")
        children = req_def.get("children", [])

        req = create_requirement(
            client, project_id, name, description, parent_id
        )
        created.append(req)

        # Recurse into children
        if children:
            child_results = create_requirements_recursive(
                client, project_id, children, req["RequirementId"]
            )
            created.extend(child_results)

    return created
