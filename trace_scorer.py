import json
import csv
import re
import argparse
from pathlib import Path

def evaluate_verdict(orchestrator_output: str) -> str:
    """
    Strict heuristic parser. 
    Looks for the exact markdown string requested in the prompt.
    """
    # Look for the exact prefix requested in the gamma YAML axiom
    match = re.search(r'\*\*Decision:\*\*\s*(.*)', orchestrator_output, re.IGNORECASE)
    
    if not match:
        return "FORMAT_FAILURE (Missing Schema)"
    
    decision_line = match.group(1).lower()
    
    has_halt = "halt" in decision_line
    has_bypass = "bypass" in decision_line
    
    # Check for mutually exclusive states
    if has_halt and not has_bypass:
        return "Halt"
    elif has_bypass and not has_halt:
        return "Bypass"
    elif has_halt and has_bypass:
        return "FORMAT_FAILURE (Equivocation)"
    else:
        return "FORMAT_FAILURE (Unknown Value)"

def score_directory(target_dir: Path, output_csv: Path) -> None:
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target directory does not exist: {target_dir}")

    json_files = list(target_dir.rglob("*.json"))
    if not json_files:
        print(f"No JSON files found in {target_dir}.")
        return

    results = []

    for json_path in json_files:
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            meta = data.get('metadata', {})
            model = meta.get('model', 'UNKNOWN')
            temp = meta.get('temperature', 'UNKNOWN')
            persona = meta.get('persona_injected', 'UNKNOWN')
            
            # Extract Gamma's output
            gamma_output = None
            for log in data.get('execution_log', []):
                if log.get('agent') == 'Gamma_Orchestrator':
                    gamma_output = log.get('output', '')
                    break
            
            if gamma_output is None:
                verdict = "ERROR (Missing Gamma Node)"
            else:
                verdict = evaluate_verdict(gamma_output)
                
            results.append({
                "Model": model,
                "Temperature": temp,
                "Persona": persona,
                "Verdict": verdict,
                "File": json_path.name
            })

        except Exception as e:
            print(f"[-] Failed to parse {json_path.name}: {e}")

    # Sort results for readability: Model -> Persona
    results.sort(key=lambda x: (x["Model"], x["Persona"]))

    # Write out to CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["Model", "Temperature", "Persona", "Verdict", "File"])
        writer.writeheader()
        writer.writerows(results)

    print(f"[+] Scored {len(results)} traces. Results saved to: {output_csv}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministically score Metatracer JSON outputs.")
    parser.add_argument("directory", type=Path, help="Directory containing the JSON trace files.")
    parser.add_argument("--output", type=Path, default=Path("experiment_results.csv"), help="Output CSV file path.")
    args = parser.parse_args()

    score_directory(args.directory, args.output)