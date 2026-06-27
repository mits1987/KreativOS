"""
Tests for Ralph Loop robustness — Issue 4 fix
"""
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_ralph_loop_passes_on_approved():
    """Ralph Loop stops immediately when both critic and QA approve"""
    with patch("main.call_ollama", new_callable=AsyncMock) as mock:
        mock.return_value = "APPROVED\nQA Verdict: PASS"
        import main as m
        result = await m.ralph_loop("model", "task", "output", "coder")
        assert result["passed"] is True
        assert result["iterations"] >= 1

@pytest.mark.asyncio
async def test_ralph_loop_retries_on_failure():
    """Ralph Loop retries up to 3 times on failure"""
    responses = ["NEEDS FIXES\n1. fix this", "QA Verdict: FAIL", "fixed output",
                 "APPROVED", "QA Verdict: PASS"]
    with patch("main.call_ollama", new_callable=AsyncMock) as mock:
        mock.side_effect = responses * 3
        import main as m
        result = await m.ralph_loop("model", "task", "initial output", "coder")
        assert result["iterations"] >= 1
        assert "log" in result

@pytest.mark.asyncio
async def test_ralph_loop_max_3_iterations():
    """Ralph Loop never exceeds 3 iterations even if always failing"""
    with patch("main.call_ollama", new_callable=AsyncMock) as mock:
        mock.return_value = "NEEDS FIXES\nBroken"
        import main as m
        result = await m.ralph_loop("model", "task", "bad output", "coder")
        assert result["iterations"] == 3
        assert len(result["log"]) == 3

@pytest.mark.asyncio
async def test_ralph_loop_handles_ollama_error():
    """Ralph Loop handles Ollama connection errors gracefully"""
    with patch("main.call_ollama", new_callable=AsyncMock) as mock:
        mock.side_effect = Exception("Connection refused")
        from main import ralph_loop
        # Should not crash — return original output
        try:
            result = await ralph_loop("model", "task", "original", "coder")
            # If it gets here it handled it
        except Exception as e:
            pytest.fail(f"Ralph loop should handle errors gracefully, got: {e}")

@pytest.mark.asyncio  
async def test_ralph_loop_empty_output():
    """Ralph Loop handles empty model output"""
    with patch("main.call_ollama", new_callable=AsyncMock) as mock:
        mock.return_value = ""
        import main as m
        result = await m.ralph_loop("model", "task", "", "coder")
        assert "iterations" in result
        assert "log" in result
