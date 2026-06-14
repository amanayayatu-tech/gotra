"""HTTP client for audited Alaya API operations used by the Judge Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv


DEFAULT_ALAYA_BASE_URL = "http://localhost:5000"


class AlayaClientError(RuntimeError):
    """Raised when the Alaya API cannot satisfy a Judge request."""


@dataclass(frozen=True)
class AlayaClient:
    """Small typed wrapper around the Alaya REST API."""

    base_url: str = DEFAULT_ALAYA_BASE_URL
    api_key: str = ""
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> AlayaClient:
        """Build a client using the automation key when configured."""

        load_dotenv()
        return cls(
            base_url=os.getenv("ALAYA_BASE_URL", DEFAULT_ALAYA_BASE_URL),
            api_key=os.getenv("ALAYA_AUTOMATION_API_KEY")
            or os.getenv("ALAYA_API_KEY", ""),
            timeout_seconds=float(os.getenv("ALAYA_TIMEOUT_SECONDS", "30")),
        )

    def list_human_gates(
        self,
        *,
        project_id: str | None = None,
        status: str | None = "pending",
        gate_type: str | None = None,
    ) -> list[dict[str, Any]]:
        params = _drop_none({"projectId": project_id, "status": status, "type": gate_type})
        data = self._request("GET", "/api/human-gates", params=params)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return list(data["items"])
        if isinstance(data, list):
            return data
        raise AlayaClientError("unexpected /api/human-gates response")

    def get_human_gate(self, gate_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/api/human-gates/{gate_id}")
        if not isinstance(data, dict):
            raise AlayaClientError("unexpected /api/human-gates/:id response")
        return data

    def approve_gate(self, gate_id: str, *, rationale: str) -> dict[str, Any]:
        return self._gate_decision(gate_id, "approve", {"rationale": rationale})

    def reject_gate(
        self,
        gate_id: str,
        *,
        rationale: str,
        reason_code: str = "risk_too_high",
    ) -> dict[str, Any]:
        return self._gate_decision(
            gate_id,
            "reject",
            {"rationale": rationale, "reasonCode": reason_code},
        )

    def list_knowledge(self, project_id: str, *, status: str) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            "/api/knowledge",
            params={"projectId": project_id, "status": status},
        )
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return list(data["items"])
        if isinstance(data, list):
            return data
        raise AlayaClientError("unexpected /api/knowledge response")

    def list_predictions(self, project_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/api/projects/{project_id}/predictions")
        if not isinstance(data, list):
            raise AlayaClientError("unexpected /api/projects/:id/predictions response")
        return data

    def quarantine_knowledge(self, knowledge_id: str) -> dict[str, Any]:
        data = self._request("POST", f"/api/knowledge/{knowledge_id}/quarantine", json={})
        if not isinstance(data, dict):
            raise AlayaClientError("unexpected /api/knowledge/:id/quarantine response")
        return data

    def _gate_decision(
        self,
        gate_id: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self._request("POST", f"/api/human-gates/{gate_id}/{action}", json=payload)
        if not isinstance(data, dict):
            raise AlayaClientError(f"unexpected gate {action} response")
        return data

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if json is not None:
            headers["Content-Type"] = "application/json"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(method, url, headers=headers, params=params, json=json)
        except httpx.HTTPError as exc:
            raise AlayaClientError(f"Alaya request failed: {exc}") from exc
        if response.status_code >= 400:
            raise AlayaClientError(
                f"Alaya {method} {path} failed with {response.status_code}: {response.text[:500]}"
            )
        return response.json()


def _drop_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}
