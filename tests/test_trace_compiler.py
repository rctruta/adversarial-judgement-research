import json
import pytest
from pathlib import Path
from pydantic import ValidationError
from trace_compiler import ExecutionTrace, process_directory

# --- Fixtures ---

@pytest.fixture
def valid_trace_data():
    return {
        "metadata": {
            "experiment_id": "test_001",
            "model": "gpt-4o",
            "temperature": 0.0,
            "persona_injected": "Test Persona",
            "timestamp": "2026-03-19T10:00:00"
        },
        "execution_log": [
            {
                "phase": "initial",
                "agent": "Alpha",
                "injected_context": "Context",
                "output": "Test output"
            }
        ]
    }

# --- Unit Tests: Schema Validation ---

def test_pydantic_accepts_valid_schema(valid_trace_data):
    """Proves the base contract works."""
    trace = ExecutionTrace(**valid_trace_data)
    assert trace.metadata.experiment_id == "test_001"
    assert len(trace.execution_log) == 1

def test_pydantic_fails_on_missing_key(valid_trace_data):
    """Proves the parser fails hard if a required key is dropped."""
    del valid_trace_data["metadata"]["temperature"]
    
    with pytest.raises(ValidationError) as excinfo:
        ExecutionTrace(**valid_trace_data)
    assert "temperature" in str(excinfo.value)

def test_pydantic_fails_on_extra_key(valid_trace_data):
    """Proves the parser fails hard if the LLM hallucinates new JSON keys."""
    valid_trace_data["execution_log"][0]["hallucinated_key"] = "bad data"
    
    with pytest.raises(ValidationError) as excinfo:
        ExecutionTrace(**valid_trace_data)
    assert "Extra inputs are not permitted" in str(excinfo.value)

# --- Integration Tests: Filesystem Parsing ---

def test_process_directory_success(tmp_path, valid_trace_data):
    """Tests that valid JSON is converted to MD and a summary is built."""
    # Setup isolated filesystem
    target_dir = tmp_path / "results"
    target_dir.mkdir()
    
    json_file = target_dir / "trace_1.json"
    json_file.write_text(json.dumps(valid_trace_data))

    # Execute
    process_directory(target_dir)

    # Assert Markdown file generation
    md_file = target_dir / "trace_1.md"
    assert md_file.exists()
    assert "# Trace: test_001" in md_file.read_text()

    # Assert Summary Index generation
    summary_file = target_dir / "summary.md"
    assert summary_file.exists()
    assert "[View Trace](./trace_1.md)" in summary_file.read_text()

def test_process_directory_fails_on_corrupted_json(tmp_path):
    """Tests that the pipeline halts and screams on malformed JSON strings."""
    target_dir = tmp_path / "results"
    target_dir.mkdir()
    
    json_file = target_dir / "trace_broken.json"
    json_file.write_text("{ broken_json: true, ") # Missing quotes and unclosed

    with pytest.raises(ValueError, match="Corrupted JSON"):
        process_directory(target_dir)