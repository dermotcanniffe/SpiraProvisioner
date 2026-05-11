"""
spira_setup.services.templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manage project templates, custom lists, and custom properties.

Supported custom field types (set via the ``type`` key in the JSON):
    list        — dropdown backed by a custom list  (requires ``values``)
    multilist   — multi-select backed by a custom list (requires ``values``)
    text        — free-text string
    integer     — whole number
    decimal     — floating-point number
    boolean     — yes/no toggle
    date        — date picker
    datetime    — date + time picker
    user        — Spira user picker
    release     — Spira release picker

Both list-backed types (list, multilist) live on the project *template*, not
the project itself.  Each project is associated with exactly one template;
this module looks up that template ID automatically from the project.
"""

import logging
from typing import Optional

from spira_setup.client import ARTIFACT_TYPE_NAME, SpiraClient

logger = logging.getLogger(__name__)

# Mapping from JSON type string → Spira CustomPropertyTypeId
PROPERTY_TYPE_ID = {
    "text":      1,
    "integer":   2,
    "decimal":   3,
    "boolean":   4,
    "date":      5,
    "list":      6,
    "multilist": 7,
    "user":      8,
    "release":   10,
    "datetime":  11,
}


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

    Uses a POST to create the list, then a PUT to add values, since the
    separate POST /values endpoint does not work for template-level lists.
    """
    existing = get_custom_list_by_name(client, template_id, name)
    if existing:
        logger.info(
            "Custom list '%s' already exists in template %s (id=%s) — skipping.",
            name, template_id, existing["CustomPropertyListId"],
        )
        return existing

    list_body = {"Name": name, "SortedOnValue": False}
    custom_list = client.post(
        f"project-templates/{template_id}/custom-lists", list_body
    )
    list_id = custom_list["CustomPropertyListId"]
    logger.info(
        "Created custom list '%s' in template %s (id=%s).",
        name, template_id, list_id,
    )

    put_body = {
        "CustomPropertyListId": list_id,
        "ProjectTemplateId": template_id,
        "Name": name,
        "Active": True,
        "SortedOnValue": False,
        "Values": [{"Name": v} for v in values],
    }
    client.put(
        f"project-templates/{template_id}/custom-lists/{list_id}", put_body
    )
    for value in values:
        logger.info("  Added list value '%s' to list %s.", value, list_id)

    return custom_list


# ------------------------------------------------------------------
# Custom properties — shared helpers
# ------------------------------------------------------------------

def get_custom_properties(
    client: SpiraClient, template_id: int, artifact_type_name: str
) -> list:
    """Return all custom properties for *artifact_type_name* in *template_id*."""
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
    """Return the custom property with *name* for the given artifact type, or ``None``.

    Only returns properties with a valid PropertyNumber (>= 1) to avoid
    matching broken properties created at slot 0 by a failed API call.
    """
    for prop in get_custom_properties(client, template_id, artifact_type_name):
        if (
            prop.get("Name", "").strip().lower() == name.strip().lower()
            and prop.get("PropertyNumber", 0) >= 1
        ):
            return prop
    return None


def _next_free_slot(
    client: SpiraClient, template_id: int, artifact_type_name: str
) -> int:
    """Return the lowest available PropertyNumber (1–30) for the artifact type."""
    existing = get_custom_properties(client, template_id, artifact_type_name)
    used = {p.get("PropertyNumber", 0) for p in existing}
    return next(i for i in range(1, 31) if i not in used)


def _artifact_type_id_for_name(artifact_type_name: str) -> int:
    """Map an artifact type name string back to its numeric ID."""
    reverse = {v: k for k, v in ARTIFACT_TYPE_NAME.items()}
    from spira_setup.client import ARTIFACT_TYPE
    key = reverse.get(artifact_type_name)
    if key is None:
        raise ValueError(f"Unknown artifact type name: '{artifact_type_name}'")
    return ARTIFACT_TYPE[key]


def _create_property(
    client: SpiraClient,
    template_id: int,
    artifact_type_name: str,
    property_name: str,
    type_id: int,
    extra_body: Optional[dict] = None,
    extra_params: Optional[dict] = None,
) -> dict:
    """
    Low-level helper: create a custom property at the next free slot.

    Checks for an existing property with the same name first (idempotent).
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

    slot = _next_free_slot(client, template_id, artifact_type_name)

    body: dict = {
        "Name": property_name,
        "CustomPropertyTypeId": type_id,
        "ArtifactTypeId": _artifact_type_id_for_name(artifact_type_name),
        "ProjectTemplateId": template_id,
        "PropertyNumber": slot,
    }
    if extra_body:
        body.update(extra_body)

    prop = client.post(
        f"project-templates/{template_id}/custom-properties",
        body,
        params=extra_params,
    )
    logger.info(
        "Created custom property '%s' (%s) on %s in template %s (slot %s).",
        property_name,
        next(k for k, v in PROPERTY_TYPE_ID.items() if v == type_id),
        artifact_type_name,
        template_id,
        slot,
    )
    return prop


# ------------------------------------------------------------------
# Public factory — dispatches by type string
# ------------------------------------------------------------------

def create_custom_property(
    client: SpiraClient,
    template_id: int,
    artifact_type_name: str,
    field_def: dict,
) -> dict:
    """
    Create a custom property from a field definition dict.

    Parameters
    ----------
    client:
        Authenticated :class:`SpiraClient`.
    template_id:
        Numeric ID of the project template.
    artifact_type_name:
        e.g. ``"TestCase"`` or ``"TestSet"``.
    field_def:
        Dict with at minimum ``name`` and ``type`` keys.  List/multilist
        types also require a ``values`` list.

    Returns
    -------
    dict
        The created (or pre-existing) custom property object from the API.

    Raises
    ------
    ValueError
        If the ``type`` is not recognised.
    """
    field_type = field_def.get("type", "").lower()
    field_name = field_def["name"]

    if field_type not in PROPERTY_TYPE_ID:
        raise ValueError(
            f"Custom field '{field_name}' has unsupported type '{field_type}'. "
            f"Supported types: {', '.join(PROPERTY_TYPE_ID)}"
        )

    type_id = PROPERTY_TYPE_ID[field_type]

    # List-backed types need a custom list first
    if field_type in ("list", "multilist"):
        values = field_def.get("values", [])
        if not values:
            raise ValueError(
                f"Custom field '{field_name}' of type '{field_type}' requires a "
                f"non-empty 'values' list."
            )
        custom_list = create_custom_list(
            client, template_id=template_id, name=field_name, values=values
        )
        list_id = custom_list["CustomPropertyListId"]
        return _create_property(
            client,
            template_id,
            artifact_type_name,
            field_name,
            type_id,
            extra_body={"CustomList": {"CustomPropertyListId": list_id}},
            extra_params={"custom_list_id": list_id},
        )

    # All other types are standalone — no list needed
    return _create_property(
        client, template_id, artifact_type_name, field_name, type_id
    )


# ------------------------------------------------------------------
# Legacy alias kept for backwards compatibility
# ------------------------------------------------------------------

def create_custom_list_property(
    client: SpiraClient,
    template_id: int,
    artifact_type_name: str,
    property_name: str,
    custom_list_id: int,
) -> dict:
    """Backwards-compatible wrapper — prefer :func:`create_custom_property`."""
    return _create_property(
        client,
        template_id,
        artifact_type_name,
        property_name,
        PROPERTY_TYPE_ID["list"],
        extra_body={"CustomList": {"CustomPropertyListId": custom_list_id}},
        extra_params={"custom_list_id": custom_list_id},
    )
