"""
spira_setup.client
~~~~~~~~~~~~~~~~~~
Low-level HTTP client for the Spira REST API v7.

This is the only module that knows about HTTP, authentication, and the base
URL.  All service modules call through here so that auth changes, retries, or
API version bumps only need to be made in one place.
"""

import logging
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Artifact type IDs as defined by the Spira API
ARTIFACT_TYPE = {
    "requirement": 1,
    "test_case": 2,
    "incident": 3,
    "release": 4,
    "test_run": 5,
    "task": 6,
    "test_step": 7,
    "test_set": 8,
    "document": 13,
}

# Artifact type name strings used by the custom-properties endpoint
ARTIFACT_TYPE_NAME = {
    "test_case": "TestCase",
    "test_set": "TestSet",
    "release": "Release",
    "requirement": "Requirement",
    "incident": "Incident",
    "task": "Task",
}


class SpiraClient:
    """Thin wrapper around the Spira REST API v7."""

    def __init__(self, base_url: str, username: str, api_key: str):
        """
        Parameters
        ----------
        base_url:
            Root URL of the Spira instance, e.g.
            ``https://mycompany.spiraservice.net/``
        username:
            Spira username.
        api_key:
            Spira API key / RSS token, including curly braces,
            e.g. ``{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}``.
        """
        # Normalise: ensure the service path is appended exactly once
        base_url = base_url.rstrip("/")
        self._service_url = f"{base_url}/Services/v7_0/RestService.svc/"
        self._auth_params = {"username": username, "api-key": api_key}
        self._session = self._build_session()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_session() -> requests.Session:
        """Return a session with automatic retries on transient errors."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        return session

    def _url(self, path: str) -> str:
        """Build a full service URL from a relative path."""
        return urljoin(self._service_url, path)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json: Optional[Any] = None,
    ) -> Any:
        """
        Execute an authenticated request and return the parsed JSON body.

        Raises
        ------
        requests.HTTPError
            On any non-2xx response, with the response body included in the
            error message to aid debugging.
        """
        all_params = {**self._auth_params, **(params or {})}
        url = self._url(path)

        logger.debug("%s %s params=%s", method, url, all_params)

        response = self._session.request(
            method, url, params=all_params, json=json
        )

        if not response.ok:
            raise requests.HTTPError(
                f"{method} {url} returned {response.status_code}: "
                f"{response.text}",
                response=response,
            )

        # Some endpoints return 200 with an empty body
        if response.text.strip():
            return response.json()
        return None

    # ------------------------------------------------------------------
    # Public convenience methods
    # ------------------------------------------------------------------

    def get(self, path: str, *, params: Optional[dict] = None) -> Any:
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        body: Any = None,
        *,
        params: Optional[dict] = None,
    ) -> Any:
        return self._request("POST", path, params=params, json=body)

    def put(
        self,
        path: str,
        body: Any = None,
        *,
        params: Optional[dict] = None,
    ) -> Any:
        return self._request("PUT", path, params=params, json=body)

    def delete(self, path: str, *, params: Optional[dict] = None) -> Any:
        return self._request("DELETE", path, params=params)
