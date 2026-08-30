"""SPA-serving tests: frontend/dist mounted at "/" with a non-API 404 fallback.

See app.main.create_app — these exercise the actual `frontend/dist` on disk
(built by `npm run build`, see Task 9), not a fixture, so they double as a
smoke test that the checked-in build is servable.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import FRONTEND_DIST

pytestmark = pytest.mark.skipif(
    not FRONTEND_DIST.is_dir(),
    reason="frontend/dist not built (run `npm run build` in frontend/)",
)


def test_root_serves_index_html(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="app">' in response.text


def test_deep_link_route_falls_back_to_index_html(client: TestClient) -> None:
    """A client-side route like /templates/5/build isn't a real file — it should
    still resolve to the SPA shell (e.g. on a hard refresh) rather than a 404.
    """
    response = client.get("/templates/5/build")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="app">' in response.text


def test_api_404_stays_json_not_index_html(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}


def test_api_health_still_json_alongside_spa_mount(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
