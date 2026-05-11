"""
spira_setup.services.templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manage project templates, custom lists, and custom properties.

Custom fields in Spira are a two-step process:
  1. Create a Custom List with its allowed values.
  2. Create a Custom Property on the desired artifact type that references
     that list.

Both operations live on the project *template*, not the project itself.
Each project is associated with exactly one template; this module looks up
that template ID automatically from the project.
"""

import logging
from typing import Optional

from spira_setup.client import ARTIFACT_TYPE_NAME, SpiraClient

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Template lookup
# ------------------------------------------------------------------

def get_template_for_project(client: SpiraClient, project_id: int) -> dict:
    """
    Return the project template associated with *project_id*.

    Raises
    ------
    ValueError
        If the project has no associated template.
    """
    project = client.get(f"projects/{project_id}")
    template_id = project.get("ProjectTemplateId")
    if not template_id:
        raise ValueError(
            f"Project {project_id} has no ProjectTemplateId in its API response."
        )
    template = client.get(f"project-templates/{template_id}")
    logger.debug("Project %s uses template %s.", project_id, template_id)
    return template


# ------------------------------------------------------------------
# Custom lists
# ------------------------------------------------------------------

def get_custom_lists(client: SpiraClient, template_id: int) -> list:
    """Return all custom lists defined in *template_id*."""
    return client.get(f"project-templates/{template_id}/custom-lists") or []


def get_custom_list_by_name(
    client: SpiraClient, template_id: int, name: str
) -> Optional[dict]:
    """Return the custom list with *name* in *template_id*, or ``None``."""
    for lst in get_custom_lists(client, template_id):
        if lst.get("Name", "").strip().lower() == name.strip().lower():
            return lst
    return None


def create_custom_list(
    client: SpiraClient,
    template_id: int,
    name: str,
    values: list[str],
) -> dict:
    """
    Create a custom list with the given *values* in *template_id*.

    If a list with *name* already exists its existing record is returned
    (idempotent — values are not re-added).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    template_id:
        Numeric ID of the project template.
    name:
        Display name for the custom list.
    values:
        List of string values to add to the list.

    Returns
    -------
    dict
        The created (or pre-existing) custom list object from the API.
    """
    existing = get_custom_list_by_name(client, template_id, name)
    if existing:
        logger.info(
            "Custom list '%s' already exists in template %s (id=%s) — skipping.",
            name, template_id, existing["CustomPropertyListId"],
        )
        return existing

    # Create the list itself
    list_body = {"Name": name, "SortedOnValue": False}
    custom_list = client.post(
        f"project-templates/{template_id}/custom-lists", list_body
    )
    list_id = custom_list["CustomPropertyListId"]
    logger.info(
        "Created custom list '%s' in template %s (id=%s).",
        name, template_id, list_id,
    )

    # Add each value
    for value in values:
        value_body = {"Name": value}
        client.post(
            f"project-templates/{template_id}/custom-lists/{list_id}/values",
            value_body,
        )
        logger.info("  Added list value '%s' to list %s.", value, list_id)

    return custom_list


# ------------------------------------------------------------------
# Custom properties
# ------------------------------------------------------------------

def get_custom_properties(
    client: SpiraClient, template_id: int, artifact_type_name: str
) -> list:
    """
    Return all custom properties for *artifact_type_name* in *template_id*.

    *artifact_type_name* must be one of the values in
    :data:`spira_setup.client.ARTIFACT_TYPE_NAME`.
    """
    return (
        client.get(
            f"project-templates/{template_id}/custom-properties/{artifact_type_name}"
        )
        or []
    )


def get_custom_property_by_name(
    client: SpiraClient,
    template_id: int,
    artifact_type_name: str,
    name: str,
) -> Optional[dict]:
    """Return the custom property with *name* for the given artifact type, or ``None``."""
    for prop in get_custom_properties(client, template_id, artifact_type_name):
        if prop.get("Name", "").strip().lower() == name.strip().lower():
            return prop
    return None


def create_custom_list_property(
    client: SpiraClient,
    template_id: int,
    artifact_type_name: str,
    property_name: str,
    custom_list_id: int,
) -> dict:
    """
    Create a List-type custom property on *artifact_type_name* backed by
    *custom_list_id*.

    If a property with *property_name* already exists it is returned as-is
    (idempotent).

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    template_id:
        Numeric ID of the project template.
    artifact_type_name:
        e.g. ``"TestCase"`` or ``"TestSet"``.
    property_name:
        Display name for the custom property field.
    custom_list_id:
        ID of the custom list that backs this property.

    Returns
    -------
    dict
        The created (or pre-existing) custom property object from the API.
    """
    existing = get_custom_property_by_name(
        client, template_id, artifact_type_name, property_name
    )
    if existing:
        logger.info(
            "Custom property '%s' already exists on %s in template %s — skipping.",
            property_name, artifact_type_name, template_id,
        )
        return existing

    body = {
        "Name": property_name,
        "CustomPropertyTypeId": 6,  # 6 = List type in Spira
        "CustomPropertyListId": custom_list_id,
        "ArtifactTypeId": _artifact_type_id_for_name(artifact_type_name),
    }

    prop = client.post(
        f"project-templates/{template_id}/custom-properties"
        f"?custom_list_id={custom_list_id}",
        body,
    )
    logger.info(
        "Created custom property '%s' on %s in template %s.",
        property_name, artifact_type_name, template_id,
    )
    return prop


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _artifact_type_id_for_name(artifact_type_name: str) -> int:
    """Map an artifact type name string back to its numeric ID."""
    reverse = {v: k for k, v in ARTIFACT_TYPE_NAME.items()}
    from spira_setup.client import ARTIFACT_TYPE
    key = reverse.get(artifact_type_name)
    if key is None:
        raise ValueError(f"Unknown artifact type name: '{artifact_type_name}'")
    return ARTIFACT_TYPE[key]
