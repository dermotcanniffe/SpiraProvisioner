"""
spira_setup.services.associations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create and look up associations (links) between Spira artifacts.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Maps structure-file type strings (camelCase) to Spira ArtifactTypeId values.
ASSOCIATION_TYPE_MAP = {
    "requirement": 1,
    "testCase": 2,
    "incident": 3,
    "release": 4,
    "task": 6,
    "risk": 14,
}

# Maps type strings to summary dict keys used by the runner.
_TYPE_TO_SUMMARY_KEY = {
    "requirement": "requirements",
    "testCase": "test_cases",
    "incident": "incidents",
    "release": "releases",
    "task": "tasks",
    "risk": "risks",
}

# Maps type strings to the ID field name in each summary entry.
_TYPE_TO_ID_FIELD = {
    "requirement": "RequirementId",
    "testCase": "TestCaseId",
    "incident": "IncidentId",
    "release": "ReleaseId",
    "task": "TaskId",
    "risk": "RiskId",
}


def _resolve_artifact_type_id(type_str: str) -> Optional[int]:
    """
    Map a type string to its numeric Spira ArtifactTypeId.

    Returns the numeric ID if *type_str* is a valid key in
    :data:`ASSOCIATION_TYPE_MAP`, or ``None`` if the type is not recognised.
    """
    type_id = ASSOCIATION_TYPE_MAP.get(type_str)
    if type_id is None:
        logger.error(
            "Invalid artifact type '%s'. Valid types: %s",
            type_str,
            ", ".join(ASSOCIATION_TYPE_MAP.keys()),
        )
    return type_id


def _get_existing_associations(
    client, project_id: int, artifact_type_id: int, artifact_id: int
) -> list:
    """
    Fetch existing associations for a given source artifact.

    Calls ``GET projects/{project_id}/artifacts/{artifact_type_id}/{artifact_id}/associations``
    and returns the list of association dicts. If the API call fails for any
    reason, logs a warning and returns an empty list so that creation can
    proceed (the worst case is a duplicate association attempt which the API
    will handle).
    """
    path = (
        f"projects/{project_id}/associations/{artifact_type_id}"
        f"/{artifact_id}"
    )
    try:
        result = client.get(path)
        return result if result is not None else []
    except Exception as exc:
        logger.warning(
            "Failed to retrieve existing associations for artifact "
            "type %d id %d in project %d: %s",
            artifact_type_id,
            artifact_id,
            project_id,
            exc,
        )
        return []


def _association_exists(
    existing: list, dest_type_id: int, dest_id: int
) -> bool:
    """
    Check whether an association to a specific destination already exists.

    Scans *existing* (a list of association dicts returned by the API) for an
    entry whose ``DestArtifactTypeId`` and ``DestArtifactId`` match the given
    destination.
    """
    return any(
        entry.get("DestArtifactTypeId") == dest_type_id
        and entry.get("DestArtifactId") == dest_id
        for entry in existing
    )


def _resolve_artifact_id(
    name: str, type_str: str, summary: dict, product_name: str
) -> Optional[int]:
    """
    Look up an artifact name in the summary to get its numeric ID.

    Uses :data:`_TYPE_TO_SUMMARY_KEY` to find the correct list within
    *summary* for the given *type_str*, then searches for an entry whose
    ``"name"`` and ``"product"`` fields match the provided *name* and
    *product_name*.

    Returns the numeric artifact ID if found, or ``None`` if the name
    cannot be resolved (with an error logged).
    """
    summary_key = _TYPE_TO_SUMMARY_KEY.get(type_str)
    if summary_key is None:
        logger.error(
            "Cannot resolve artifact ID: unknown type '%s' for artifact '%s'.",
            type_str,
            name,
        )
        return None

    entries = summary.get(summary_key, [])
    for entry in entries:
        if entry.get("name") == name and entry.get("product") == product_name:
            return entry.get("id")

    # Log available names at debug level to help diagnose mismatches
    available_names = [e.get("name") for e in entries if e.get("product") == product_name]
    logger.error(
        "Cannot resolve artifact ID: '%s' of type '%s' not found in summary for product '%s'. "
        "Available names: %s",
        name,
        type_str,
        product_name,
        available_names,
    )
    return None


def _create_requirement_test_coverage(
    client, project_id: int, requirement_id: int, test_case_id: int,
    source_name: str, dest_name: str, comment: str = None,
) -> bool:
    """
    Create a requirement ↔ test case coverage link using the dedicated endpoint.

    This makes the test case appear in the requirement's Test Cases tab and
    enables Spira's traceability/coverage model.

    Returns True on success, False on failure.
    """
    body = {
        "RequirementId": requirement_id,
        "TestCaseId": test_case_id,
    }
    path = f"projects/{project_id}/requirements/test-cases"
    try:
        logger.info(
            "Creating test coverage: POST %s -> %s",
            path,
            body,
        )
        client.post(path, body)
        logger.info(
            "Created test coverage '%s' (requirement) -> '%s' (testCase) in project %d.",
            source_name,
            dest_name,
            project_id,
        )
        return True
    except Exception as exc:
        # 409 or similar may mean coverage already exists
        logger.warning(
            "Failed to create test coverage '%s' -> '%s' in project %d: %s",
            source_name,
            dest_name,
            project_id,
            exc,
        )
        return False


def _link_task_to_requirement(
    client, project_id: int, requirement_id: int, task_id: int,
    source_name: str, dest_name: str, comment: str = None,
) -> bool:
    """
    Link a task to a requirement by updating the task's RequirementId field.

    This makes the task appear in the requirement's Tasks tab and enables
    Spira's progress/effort rollup on the requirement.

    Returns True on success, False on failure.
    """
    path = f"projects/{project_id}/tasks/{task_id}"
    try:
        # GET the current task to preserve all fields (Spira requires full object on PUT)
        task = client.get(path)
        if task is None:
            logger.warning(
                "Could not retrieve task id %d in project %d for requirement linking.",
                task_id,
                project_id,
            )
            return False

        task["RequirementId"] = requirement_id
        logger.info(
            "Linking task to requirement: PUT %s (RequirementId=%d)",
            path,
            requirement_id,
        )
        client.put(f"projects/{project_id}/tasks", task)
        logger.info(
            "Linked task '%s' to requirement '%s' in project %d.",
            dest_name,
            source_name,
            project_id,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Failed to link task '%s' to requirement '%s' in project %d: %s",
            dest_name,
            source_name,
            project_id,
            exc,
        )
        return False


def _link_task_to_risk(
    client, project_id: int, risk_id: int, task_id: int,
    source_name: str, dest_name: str, comment: str = None,
) -> bool:
    """
    Link a task to a risk by updating the task's RiskId field.

    This makes the task appear in the risk's Tasks tab and enables
    Spira's risk mitigation tracking.

    Returns True on success, False on failure.
    """
    path = f"projects/{project_id}/tasks/{task_id}"
    try:
        task = client.get(path)
        if task is None:
            logger.warning(
                "Could not retrieve task id %d in project %d for risk linking.",
                task_id,
                project_id,
            )
            return False

        task["RiskId"] = risk_id
        logger.info(
            "Linking task to risk: PUT %s (RiskId=%d)",
            path,
            risk_id,
        )
        client.put(f"projects/{project_id}/tasks", task)
        logger.info(
            "Linked task '%s' to risk '%s' in project %d.",
            dest_name,
            source_name,
            project_id,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Failed to link task '%s' to risk '%s' in project %d: %s",
            dest_name,
            source_name,
            project_id,
            exc,
        )
        return False


def _create_release_test_case_mapping(
    client, project_id: int, release_id: int, test_case_id: int,
    source_name: str, dest_name: str, comment: str = None,
) -> bool:
    """
    Map a test case to a release so it appears in the release's test coverage.

    Uses the dedicated endpoint:
    POST projects/{project_id}/releases/{release_id}/test-cases

    Returns True on success, False on failure.
    """
    body = {
        "ReleaseId": release_id,
        "TestCaseId": test_case_id,
    }
    path = f"projects/{project_id}/releases/{release_id}/test-cases"
    try:
        logger.info(
            "Creating release test case mapping: POST %s -> %s",
            path,
            body,
        )
        client.post(path, body)
        logger.info(
            "Mapped test case '%s' to release '%s' in project %d.",
            dest_name,
            source_name,
            project_id,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Failed to map test case '%s' to release '%s' in project %d: %s",
            dest_name,
            source_name,
            project_id,
            exc,
        )
        return False


def create_associations(
    client, project_id: int, associations_def: list, summary: dict, product_name: str
) -> list:
    """
    Create associations between Spira artifacts.

    Iterates over *associations_def* (a list of dicts from the structure file),
    resolves each entry's types and names to numeric IDs, checks for existing
    associations (idempotency), and POSTs new ones to the Spira API.

    Parameters
    ----------
    client:
        Authenticated :class:`~spira_setup.client.SpiraClient`.
    project_id:
        Numeric ID of the target project.
    associations_def:
        List of association definitions, each with keys ``sourceType``,
        ``source``, ``destType``, ``dest``, and optionally ``comment``.
    summary:
        Runner summary dict containing previously created artifact IDs.
    product_name:
        Name of the current product (used for summary lookups).

    Returns
    -------
    list[dict]
        A list of result dicts, each with keys ``source``, ``dest``,
        ``product``, and ``status`` ("created", "skipped", or "error").
    """
    results = []

    for entry in associations_def:
        source_name = entry.get("source", "")
        dest_name = entry.get("dest", "")
        source_type_str = entry.get("sourceType", "")
        dest_type_str = entry.get("destType", "")
        comment = entry.get("comment")

        # Resolve source type
        source_type_id = _resolve_artifact_type_id(source_type_str)
        if source_type_id is None:
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "error",
            })
            continue

        # Resolve dest type
        dest_type_id = _resolve_artifact_type_id(dest_type_str)
        if dest_type_id is None:
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "error",
            })
            continue

        # Resolve source name to ID
        source_id = _resolve_artifact_id(source_name, source_type_str, summary, product_name)
        if source_id is None:
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "error",
            })
            continue

        # Resolve dest name to ID
        dest_id = _resolve_artifact_id(dest_name, dest_type_str, summary, product_name)
        if dest_id is None:
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "error",
            })
            continue

        # -----------------------------------------------------------------
        # Route to the correct endpoint based on source/dest type combo
        # -----------------------------------------------------------------

        # Requirement -> Test Case: use dedicated coverage endpoint
        if source_type_str == "requirement" and dest_type_str == "testCase":
            success = _create_requirement_test_coverage(
                client, project_id, source_id, dest_id,
                source_name, dest_name, comment,
            )
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "created" if success else "error",
            })
            continue

        # Requirement -> Task: link task to requirement via RequirementId
        if source_type_str == "requirement" and dest_type_str == "task":
            success = _link_task_to_requirement(
                client, project_id, source_id, dest_id,
                source_name, dest_name, comment,
            )
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "created" if success else "error",
            })
            continue

        # Risk -> Task: link task to risk via RiskId
        if source_type_str == "risk" and dest_type_str == "task":
            success = _link_task_to_risk(
                client, project_id, source_id, dest_id,
                source_name, dest_name, comment,
            )
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "created" if success else "error",
            })
            continue

        # Release -> Test Case: map test case to release for coverage
        if source_type_str == "release" and dest_type_str == "testCase":
            success = _create_release_test_case_mapping(
                client, project_id, source_id, dest_id,
                source_name, dest_name, comment,
            )
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "created" if success else "error",
            })
            continue

        # All other combinations: use the generic associations endpoint
        # Check idempotency
        existing = _get_existing_associations(client, project_id, source_type_id, source_id)
        if _association_exists(existing, dest_type_id, dest_id):
            logger.info(
                "Association '%s' -> '%s' already exists in project %d — skipping.",
                source_name,
                dest_name,
                project_id,
            )
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "skipped",
            })
            continue

        # Build POST body
        body = {
            "SourceArtifactTypeId": source_type_id,
            "SourceArtifactId": source_id,
            "DestArtifactTypeId": dest_type_id,
            "DestArtifactId": dest_id,
            "ArtifactLinkTypeId": 1,  # 1 = "Related To" (default link type)
        }
        if comment is not None:
            body["Comment"] = comment

        # Create the association
        path = f"projects/{project_id}/associations"
        try:
            logger.info(
                "Creating association: POST %s -> %s",
                path,
                body,
            )
            client.post(path, body)
            logger.info(
                "Created association '%s' (%s) -> '%s' (%s) in project %d.",
                source_name,
                source_type_str,
                dest_name,
                dest_type_str,
                project_id,
            )
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "created",
            })
        except Exception as exc:
            logger.warning(
                "Failed to create association '%s' -> '%s' in project %d: %s",
                source_name,
                dest_name,
                project_id,
                exc,
            )
            results.append({
                "source": source_name,
                "dest": dest_name,
                "product": product_name,
                "status": "error",
            })

    return results
