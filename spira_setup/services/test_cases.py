"""
spira_setup.services.test_cases
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create and look up test case folders and test cases within a Spira project.
"""

import logging
from typing import Optional

from spira_setup.client import SpiraClient

logger = logging.getLogger(__name__)

# Default status ID — 1 = Draft, present in all standard Spira templates
TEST_CASE_STATUS_DRAFT = 1


def _get_default_test_case_type_id(client: SpiraClient, project_id: int) -> int:
    """
    Look up the default test case type ID for the template associated with
    *project_id*.  Falls back to the first active type if no default is set.
    """
    project = client.get(f"projects/{project_id}")
    template_id = project.get("ProjectTemplateId")
    types = client.get(f"project-templates/{template_id}/test-cases/types") or []
    for t in types:
        if t.get("IsDefault"):
            return t["TestCaseTypeId"]
    if types:
        return types[0]["TestCaseTypeId"]
    raise ValueError(f"No test case types found for project {project_id}")


# ------------------------------------------------------------------
# Test case folders
# ------------------------------------------------------------------

def get_test_folders(client: SpiraClient, project_id: int) -> list:
    """Return all test case folders in *project_id*."""
    return client.get(f"projects/{project_id}/test-folders") or []


def get_test_folder_by_name(
    client: SpiraClient, project_id: int, name: str
) -> Optional[dict]:
    """Return the root-level test folder with *name*, or ``None``."""
    for folder in get_test_folders(client, project_id):
        if folder.get("Name", "").strip().lower() == name.strip().lower():
            return folder
    return None


def create_test_folder(
    client: SpiraClient,
    project_id: int,
    name: str,
    parent_folder_id: Optional[int] = None,
) -> dict:
    """
    Create a test case folder in *project_id*.

    If a folder with *name* already exists at the root level it is returned
    as-is (idempotent).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    name:
        Display name for the folder.
    parent_folder_id:
        If provided, the folder is created as a child of this folder.
        Defaults to root level (``None``).

    Returns
    -------
    dict
        The created (or pre-existing) folder object from the API.
    """
    existing = get_test_folder_by_name(client, project_id, name)
    if existing:
        logger.info(
            "Test folder '%s' already exists in project %s (id=%s) — skipping.",
            name, project_id, existing["TestCaseFolderId"],
        )
        return existing

    body: dict = {"Name": name}
    if parent_folder_id is not None:
        body["ParentTestCaseFolderId"] = parent_folder_id

    folder = client.post(f"projects/{project_id}/test-folders", body)
    logger.info(
        "Created test folder '%s' in project %s (id=%s).",
        name, project_id, folder["TestCaseFolderId"],
    )
    return folder


# ------------------------------------------------------------------
# Test cases
# ------------------------------------------------------------------

def get_test_cases_in_folder(
    client: SpiraClient, project_id: int, folder_id: int
) -> list:
    """Return all test cases in *folder_id* within *project_id*."""
    return (
        client.get(
            f"projects/{project_id}/test-folders/{folder_id}/test-cases",
            params={"starting_row": 1, "number_of_rows": 500},
        )
        or []
    )


def get_test_case_by_name_in_folder(
    client: SpiraClient, project_id: int, folder_id: int, name: str
) -> Optional[dict]:
    """Return the test case with *name* in *folder_id*, or ``None``."""
    for tc in get_test_cases_in_folder(client, project_id, folder_id):
        if tc.get("Name", "").strip().lower() == name.strip().lower():
            return tc
    return None


def create_test_case(
    client: SpiraClient,
    project_id: int,
    name: str,
    description: str = "",
    folder_id: Optional[int] = None,
    status_id: int = TEST_CASE_STATUS_DRAFT,
    type_id: Optional[int] = None,
) -> dict:
    """
    Create a test case in *project_id*, optionally inside *folder_id*.

    If a test case with *name* already exists in *folder_id* it is returned
    as-is (idempotent).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    project_id:
        Numeric ID of the parent project.
    name:
        Display name for the test case.
    description:
        Optional description / purpose of the test case.
    folder_id:
        If provided, the test case is placed in this folder.
    status_id:
        Spira test case status ID.  Defaults to Draft (1).
    type_id:
        Spira test case type ID.  If not provided, the template default is
        used automatically.

    Returns
    -------
    dict
        The created (or pre-existing) test case object from the API.
    """
    if folder_id is not None:
        existing = get_test_case_by_name_in_folder(
            client, project_id, folder_id, name
        )
        if existing:
            logger.info(
                "Test case '%s' already exists in folder %s (id=%s) — skipping.",
                name, folder_id, existing["TestCaseId"],
            )
            return existing

    if type_id is None:
        type_id = _get_default_test_case_type_id(client, project_id)

    body: dict = {
        "Name": name,
        "Description": description,
        "TestCaseStatusId": status_id,
        "TestCaseTypeId": type_id,
    }
    if folder_id is not None:
        body["TestCaseFolderId"] = folder_id

    test_case = client.post(f"projects/{project_id}/test-cases", body)
    logger.info(
        "Created test case '%s' in project %s (id=%s).",
        name, project_id, test_case["TestCaseId"],
    )
    return test_case
