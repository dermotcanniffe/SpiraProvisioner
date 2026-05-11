"""
spira_setup.runner
~~~~~~~~~~~~~~~~~~~
Orchestrates the full Spira project setup from a structure definition dict.

The runner is intentionally free of HTTP knowledge — it only calls service
functions and threads IDs between them.  The structure dict is expected to
match the shape of ``spira-structure.json``.
"""

import logging
from typing import Any

from spira_setup.client import ARTIFACT_TYPE_NAME, SpiraClient
from spira_setup.services import projects, releases, templates, test_cases

logger = logging.getLogger(__name__)


def run(client: SpiraClient, structure: dict) -> dict:
    """
    Execute the full setup described by *structure*.

    Parameters
    ----------
    client:
        An authenticated :class:`~spira_setup.client.SpiraClient`.
    structure:
        Parsed contents of ``spira-structure.json``.

    Returns
    -------
    dict
        A summary of every resource that was created or already existed,
        keyed by resource type.
    """
    summary: dict[str, list] = {
        "program": [],
        "products": [],
        "releases": [],
        "custom_lists": [],
        "custom_properties": [],
        "test_folders": [],
        "test_cases": [],
    }

    program_def = structure.get("program", {})
    program_name = program_def.get("name", "")

    # ------------------------------------------------------------------
    # 1. Verify the program exists (programs cannot be created via API)
    # ------------------------------------------------------------------
    program = projects.get_program_by_name(client, program_name)
    if program:
        program_id = program.get("ProjectGroupId") or program.get("ProgramId")
        logger.info("Found program '%s' (id=%s).", program_name, program_id)
        summary["program"].append({"name": program_name, "id": program_id})
    else:
        logger.warning(
            "Program '%s' was not found via the API.  "
            "Programs must be created manually in the Spira admin UI.  "
            "Products will be created without a program association.",
            program_name,
        )
        program_id = None

    # ------------------------------------------------------------------
    # 2. Products
    # ------------------------------------------------------------------
    for product_def in program_def.get("products", []):
        product_name = product_def["name"]
        logger.info("--- Processing product: %s ---", product_name)

        project = projects.create_project(
            client,
            name=product_name,
            program_id=program_id,
        )
        project_id = project["ProjectId"]
        summary["products"].append({"name": product_name, "id": project_id})

        # Resolve the project template once per product
        template = templates.get_template_for_project(client, project_id)
        template_id = template["ProjectTemplateId"]

        # --------------------------------------------------------------
        # 3. Releases
        # --------------------------------------------------------------
        for release_def in product_def.get("releases", []):
            release = releases.create_release(
                client,
                project_id=project_id,
                name=release_def["name"],
            )
            summary["releases"].append(
                {
                    "name": release_def["name"],
                    "id": release["ReleaseId"],
                    "product": product_name,
                }
            )

        # --------------------------------------------------------------
        # 4. Custom fields
        # --------------------------------------------------------------
        custom_fields_def = product_def.get("customFields", {})

        _setup_custom_fields(
            client,
            template_id=template_id,
            artifact_key="testCases",
            artifact_type_name=ARTIFACT_TYPE_NAME["test_case"],
            fields_def=custom_fields_def.get("testCases", []),
            summary=summary,
            product_name=product_name,
        )

        _setup_custom_fields(
            client,
            template_id=template_id,
            artifact_key="testSets",
            artifact_type_name=ARTIFACT_TYPE_NAME["test_set"],
            fields_def=custom_fields_def.get("testSets", []),
            summary=summary,
            product_name=product_name,
        )

        # --------------------------------------------------------------
        # 5. Test folders and test cases
        # --------------------------------------------------------------
        for folder_def in product_def.get("testFolders", []):
            folder_name = folder_def["name"]
            folder = test_cases.create_test_folder(
                client, project_id=project_id, name=folder_name
            )
            folder_id = folder["TestCaseFolderId"]
            summary["test_folders"].append(
                {"name": folder_name, "id": folder_id, "product": product_name}
            )

            for tc_def in folder_def.get("testCases", []):
                tc = test_cases.create_test_case(
                    client,
                    project_id=project_id,
                    name=tc_def["name"],
                    description=tc_def.get("description", ""),
                    folder_id=folder_id,
                )
                summary["test_cases"].append(
                    {
                        "name": tc_def["name"],
                        "id": tc["TestCaseId"],
                        "folder": folder_name,
                        "product": product_name,
                    }
                )

    return summary


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _setup_custom_fields(
    client: SpiraClient,
    template_id: int,
    artifact_key: str,
    artifact_type_name: str,
    fields_def: list,
    summary: dict,
    product_name: str,
) -> None:
    """Create custom lists and their backing custom properties."""
    for field_def in fields_def:
        if field_def.get("type") != "list":
            logger.warning(
                "Custom field '%s' has unsupported type '%s' — skipping.",
                field_def.get("name"),
                field_def.get("type"),
            )
            continue

        field_name = field_def["name"]
        values = field_def.get("values", [])

        # Step 1: custom list
        custom_list = templates.create_custom_list(
            client,
            template_id=template_id,
            name=field_name,
            values=values,
        )
        list_id = custom_list["CustomPropertyListId"]
        summary["custom_lists"].append(
            {
                "name": field_name,
                "id": list_id,
                "artifact": artifact_type_name,
                "product": product_name,
            }
        )

        # Step 2: custom property backed by that list
        prop = templates.create_custom_list_property(
            client,
            template_id=template_id,
            artifact_type_name=artifact_type_name,
            property_name=field_name,
            custom_list_id=list_id,
        )
        summary["custom_properties"].append(
            {
                "name": field_name,
                "id": prop.get("CustomPropertyId"),
                "artifact": artifact_type_name,
                "product": product_name,
            }
        )
