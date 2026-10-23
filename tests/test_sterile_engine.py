import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from sterile_engine import MatrixEngine

# ---------------------------------------------------------
# Tier 1: Mocked Unit Tests (Runs by default)
# ---------------------------------------------------------

@pytest.mark.asyncio
@patch('sterile_engine.acompletion')
async def test_matrix_engine_mocked_success(mock_acompletion, tmp_path):
    """Proves the engine routes data correctly without hitting the internet."""
    
    # Force the mock to return a known string
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock(message=AsyncMock(content="MOCKED_OUTPUT"))]
    mock_acompletion.return_value = mock_response

    # Setup dummy YAML
    config_path = tmp_path / "dummy.yaml"
    config_path.write_text("""
experiment_id: "test_mock"
models: ["mock-model"]
temperatures: [0.0]
scenario: "Test scenario"
axioms: {alpha: "A", beta: "B", gamma: "C"}
    """)

    engine = MatrixEngine(str(config_path))

    custom_out = tmp_path / "results"
    custom_out.mkdir()
    engine.output_dir = str(custom_out)
    
    await engine.run()

    # Assert the mock was called the correct number of times (Phase 1: 2, Phase 2: 2, Phase 3: 1)
    assert mock_acompletion.call_count == 5
    
    # Assert it saved the payload
    saved_files = list(Path(engine.output_dir).glob("*.json"))
    assert len(saved_files) == 1
    assert "MOCKED_OUTPUT" in saved_files[0].read_text()

@pytest.mark.asyncio
@patch('sterile_engine.acompletion')
async def test_matrix_engine_handles_api_failure(mock_acompletion, tmp_path):
    """Proves the engine doesn't crash the whole run if one API call times out."""
    
    # Force the mock to simulate a network crash
    mock_acompletion.side_effect = Exception("502 Bad Gateway")

    config_path = tmp_path / "dummy_fail.yaml"
    config_path.write_text("""
experiment_id: "test_fail"
models: ["mock-model"]
temperatures: [0.0]
scenario: "Fail scenario"
axioms: {alpha: "A", beta: "B", gamma: "C"}
    """)

    engine = MatrixEngine(str(config_path))
    custom_out = tmp_path / "results"
    custom_out.mkdir()
    engine.output_dir = str(custom_out)
    
    await engine.run()

    # Assert it still saved the JSON, but recorded the error instead of crashing
    saved_files = list(Path(engine.output_dir).glob("*.json"))
    trace_content = saved_files[0].read_text()
    assert "API EXECUTION FAILED: 502 Bad Gateway" in trace_content

# ---------------------------------------------------------
# Tier 2: Live Integration Tests (Opt-In only)
# ---------------------------------------------------------

@pytest.mark.live
@pytest.mark.asyncio
async def test_matrix_engine_live_execution(tmp_path):
    """
    WARNING: Hits the real API. Requires .env with valid keys.
    Run only via: pytest --run-live
    """
    from pathlib import Path # Ensure this is imported at the top if not already
    
    config_path = tmp_path / "live_dummy.yaml"
    config_path.write_text("""
experiment_id: "test_live_network"
models: ["gemini/gemini-3-flash"] 
temperatures: [0.0]
scenario: "Say the word 'ACKNOWLEDGE'."
axioms: {alpha: "Be brief.", beta: "Be brief.", gamma: "Be brief."}
    """)

    engine = MatrixEngine(str(config_path))
    
    # FIX: Explicitly create the directory before overriding
    custom_out = tmp_path / "results_live"
    custom_out.mkdir()
    engine.output_dir = str(custom_out)
    
    await engine.run()

    saved_files = list(Path(engine.output_dir).glob("*.json"))
    assert len(saved_files) == 1
    assert len(saved_files[0].read_text()) > 100