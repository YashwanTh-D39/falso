import pytest
from app.tools.maps_tool import MapsTool
from app.tools.github_tool import GitHubTool
from app.tools.pypi_tool import PyPITool


@pytest.mark.asyncio
async def test_maps_tool_matching():
    """Verify prompt matching for location and maps queries."""
    res1 = MapsTool.match_prompt("coffee near me")
    assert res1 is not None
    assert "query" in res1

    res2 = MapsTool.match_prompt("directions to airport")
    assert res2 is not None


@pytest.mark.asyncio
async def test_maps_tool_execution():
    """Verify MapsTool returns geocoded coordinates and map links."""
    tool = MapsTool()
    res = await tool.execute(query="New York")
    assert res.success is True
    assert "Location Found" in res.data or "New York" in res.data


@pytest.mark.asyncio
async def test_github_tool_matching_and_execution():
    """Verify GitHubTool matches repo queries and fetches repos."""
    res_match = GitHubTool.match_prompt("github repo for fastapi")
    assert res_match is not None
    assert res_match.get("query") == "fastapi"

    tool = GitHubTool()
    res = await tool.execute(query="fastapi")
    assert res.success is True
    assert "GitHub Search Results" in res.data or "fastapi" in res.data.lower()


@pytest.mark.asyncio
async def test_pypi_tool_matching_and_execution():
    """Verify PyPITool matches package version requests and fetches PyPI details."""
    res_match = PyPITool.match_prompt("latest version of fastapi")
    assert res_match is not None
    assert res_match.get("package") == "fastapi"

    tool = PyPITool()
    res = await tool.execute(package="fastapi")
    assert res.success is True
    assert "Package: fastapi" in res.data
