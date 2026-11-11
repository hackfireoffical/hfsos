"""Search endpoints for supported platforms."""
from fastapi import APIRouter, HTTPException, Query

from app.providers import github, modrinth, youtube

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/github/search")
async def github_search(q: str = Query(min_length=1, max_length=200), limit: int = 10):
    try:
        return {"results": await github.search_repositories(q, limit)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub provider failed: {type(exc).__name__}") from exc


@router.get("/github/{owner}/{repo}/latest-release")
async def github_latest_release(owner: str, repo: str):
    try:
        result = await github.latest_release(owner, repo)
        if result is None:
            raise HTTPException(status_code=404, detail="No published release found.")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub provider failed: {type(exc).__name__}") from exc


@router.get("/modrinth/search")
async def modrinth_search(
    q: str = Query(min_length=1, max_length=200),
    project_type: str | None = None,
    limit: int = 10,
):
    try:
        return {"results": await modrinth.search_projects(q, project_type, limit)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Modrinth provider failed: {type(exc).__name__}") from exc


@router.get("/modrinth/{project_id_or_slug}/versions")
async def modrinth_versions(
    project_id_or_slug: str,
    game_version: str | None = None,
    loader: str | None = None,
    limit: int = 20,
):
    try:
        return {"results": await modrinth.project_versions(project_id_or_slug, game_version, loader, limit)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Modrinth provider failed: {type(exc).__name__}") from exc


@router.get("/youtube/search")
async def youtube_search(q: str = Query(min_length=1, max_length=200), limit: int = 10):
    try:
        return await youtube.search_videos(q, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"YouTube providers failed: {type(exc).__name__}") from exc
