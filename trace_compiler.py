import json
import argparse
from pathlib import Path
from pydantic import BaseModel, ConfigDict, ValidationError

# ---------------------------------------------------------
# Strict Schema Definitions
# No defaults. Fails immediately on missing or extra keys.
# ---------------------------------------------------------

class TraceMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    experiment_id: str
    model: str
    temperature: float
    persona_injected: str
    timestamp: str

class LogEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    phase: str
    agent: str
    injected_context: str
    output: str

class ExecutionTrace(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    metadata: TraceMetadata
    execution_log: list[LogEntry]

# ---------------------------------------------------------
# Markdown Generation & Aggregation
# ---------------------------------------------------------

def trace_to_markdown(trace: ExecutionTrace) -> str:
    """Maps the validated Pydantic object to a Markdown string."""
    md = [
        f"# Trace: {trace.metadata.experiment_id}",
        f"**Model:** `{trace.metadata.model}` | **Temp:** `{trace.metadata.temperature}` | **Persona:** `{trace.metadata.persona_injected}`",
        f"**Timestamp:** `{trace.metadata.timestamp}`",
        "---"
    ]

    for log in trace.execution_log:
        md.extend([
            f"## Phase: {log.phase} | Agent: {log.agent}",
            f"> **Injected Context:** {log.injected_context}\n",
            f"{log.output}\n",
            "---\n"
        ])

    return "\n".join(md)

def generate_summary_index(target_dir: Path, successful_traces: list[tuple[ExecutionTrace, Path]]) -> None:
    """Compiles a Markdown table linking to all successfully parsed traces."""
    if not successful_traces:
        return

    # Sort by model, then by persona for grouped readability
    successful_traces.sort(key=lambda x: (x[0].metadata.model, x[0].metadata.persona_injected))
    
    experiment_id = successful_traces[0][0].metadata.experiment_id

    md = [
        f"# Experiment Summary: {experiment_id}",
        f"**Total Successful Traces:** {len(successful_traces)}\n",
        "| Model | Temp | Persona | Trace Log |",
        "|---|---|---|---|"
    ]

    for trace, md_path in successful_traces:
        # Create a relative link from the summary file to the individual markdown file
        relative_link = md_path.name
        meta = trace.metadata
        md.append(f"| `{meta.model}` | `{meta.temperature}` | `{meta.persona_injected}` | [View Trace](./{relative_link}) |")

    summary_path = target_dir / "summary.md"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))
    
    print(f"[+] Generated master index: {summary_path}")

def process_directory(target_dir: Path) -> None:
    """Sweeps a directory for JSON traces, validates, writes MD files, and builds an index."""
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target directory does not exist: {target_dir}")

    json_files = list(target_dir.rglob("*.json"))
    if not json_files:
        print(f"No JSON files found in {target_dir}.")
        return

    successful_traces = []

    for json_path in json_files:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            validated_trace = ExecutionTrace(**raw_data)
            markdown_content = trace_to_markdown(validated_trace)
            
            md_path = json_path.with_suffix('.md')
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
                
            successful_traces.append((validated_trace, md_path))

        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted JSON in {json_path}: {e}")
        except ValidationError as e:
            raise ValueError(f"Schema violation in {json_path}. Metatracer contract broken:\n{e}")

    print(f"[*] Processed {len(successful_traces)}/{len(json_files)} traces successfully.")
    
    generate_summary_index(target_dir, successful_traces)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compile Metatracer JSON outputs into Markdown and build an index.")
    parser.add_argument("directory", type=Path, help="Directory containing the JSON trace files.")
    args = parser.parse_args()

    process_directory(args.directory)