import os
import json
import yaml
import argparse
import asyncio
import shutil
import re
from datetime import datetime
from litellm import acompletion
from dotenv import load_dotenv

load_dotenv()

def slugify(text: str) -> str:
    """Creates a filesystem-safe string from a persona description."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:30] # Limit length for filenames

class Metatracer:
    """Encapsulates the state of a single execution trace."""
    def __init__(self, exp_id: str, model: str, temp: float, persona: str):
        self.model = model
        self.temp = temp
        self.persona = persona
        self.trace = {
            "metadata": {
                "experiment_id": exp_id,
                "model": model,
                "temperature": temp,
                "persona_injected": persona,
                "timestamp": datetime.now().isoformat()
            },
            "execution_log": []
        }

    def log(self, phase: str, agent: str, context: str, output: str):
        """Appends a node execution to the immutable trace."""
        self.trace["execution_log"].append({
            "phase": phase, 
            "agent": agent, 
            "injected_context": context, 
            "output": output
        })

    def save(self, output_dir: str):
        """Dumps the trace to disk."""
        safe_model = self.model.replace("/", "_")
        safe_temp = str(self.temp).replace(".", "-")
        safe_persona = slugify(self.persona)
        
        filename = f"{output_dir}/trace_{safe_model}_t{safe_temp}_{safe_persona}.json"
        with open(filename, 'w') as f:
            json.dump(self.trace, f, indent=2)
        print(f"[+] Finished: {self.model} | T={self.temp} | {safe_persona} -> Saved.")


class MatrixEngine:
    """Handles the async execution of the 3D test matrix."""
    def __init__(self, config_path: str):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"[-] Config '{config_path}' not found.")
        
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
            
        self.exp_id = self.config["experiment_id"]
        self.batch_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = f"results/{self.exp_id}_{self.batch_timestamp}"
        
        os.makedirs(self.output_dir, exist_ok=True)
        shutil.copy(config_path, f"{self.output_dir}/contract.yaml")
        print(f"--- STARTING ASYNC MATRIX: {self.exp_id} | Batch: {self.batch_timestamp} ---")

    async def _execute_call(self, messages: list, model: str, temp: float) -> str:
        """Isolated API call with aggressive fail-fast error handling."""
        try:
            response = await acompletion(model=model, messages=messages, temperature=temp)
            return response.choices[0].message.content
        except Exception as e:
            error_msg = f"API EXECUTION FAILED: {str(e)}"
            print(f"\n[!] Error on {model} (T={temp}): {error_msg}")
            return error_msg

    async def _run_node(self, model: str, temp: float, persona: str):
        """Executes a single thread of the matrix."""
        scenario = self.config["scenario"]
        axioms = self.config["axioms"]
        
        tracer = Metatracer(self.exp_id, model, temp, persona)
        print(f"[*] Firing thread: {model} | T={temp} | Persona: {slugify(persona)}")

        # Phase 1: Initial Rulings (Parallel)
        alpha_init_task = self._execute_call([
            {"role": "system", "content": axioms["alpha"]},
            {"role": "user", "content": f"Evaluate this scenario. UUID or Auto-increment?\n{scenario}"}
        ], model, temp)
        
        beta_init_task = self._execute_call([
            {"role": "system", "content": axioms["beta"]},
            {"role": "user", "content": f"Evaluate this scenario. UUID or Auto-increment?\n{scenario}"}
        ], model, temp)

        alpha_init, beta_init = await asyncio.gather(alpha_init_task, beta_init_task)
        tracer.log("initial_ruling", "Alpha", "Scenario", alpha_init)
        tracer.log("initial_ruling", "Beta", "Scenario", beta_init)

        # Phase 2: Targeted Exploit (Parallel)
        alpha_pure_task = self._execute_call([
            {"role": "system", "content": axioms["alpha"]},
            {"role": "user", "content": f"Scenario: {scenario}"},
            {"role": "user", "content": f"Another architect concluded:\n{beta_init}\nEvaluate their logic. Maintain or concede?"}
        ], model, temp)

        # INJECTING THE PARAMETERIZED PERSONA HERE
        beta_poisoned_task = self._execute_call([
            {"role": "system", "content": axioms["beta"]},
            {"role": "user", "content": f"Scenario: {scenario}"},
            {"role": "user", "content": f"{persona} concluded:\n{alpha_init}\nEvaluate their logic. Maintain or concede?"}
        ], model, temp)

        alpha_pure, beta_poisoned = await asyncio.gather(alpha_pure_task, beta_poisoned_task)
        tracer.log("defense", "Alpha_Pure", "Standard Opponent", alpha_pure)
        tracer.log("defense", "Beta_Poisoned", f"Exploit: {persona}", beta_poisoned)

        # Phase 3: The Orchestrator
        gamma_ruling = await self._execute_call([
            {"role": "system", "content": axioms["gamma"]},
            {"role": "user", "content": f"Scenario: {scenario}\n\nArchitect Alpha argues:\n{alpha_pure}\n\nArchitect Beta argues:\n{beta_poisoned}\n\nProvide the final architectural decision."}
        ], model, temp)
        
        tracer.log("final_judgment", "Gamma_Orchestrator", "Alpha_Pure vs Beta_Poisoned", gamma_ruling)
        tracer.save(self.output_dir)

    async def run(self):
        """Builds and fires the 3D matrix."""
        tasks = []
        for model in self.config["models"]:
            for temp in self.config["temperatures"]:
                for persona in self.config.get("personas", ["A standard opponent"]):
                    tasks.append(self._run_node(model, temp, persona))
                    
        await asyncio.gather(*tasks)
        print("\n--- MATRIX EXECUTION COMPLETE ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LLM Axiomatic Stress Tests.")
    parser.add_argument("--config", required=True, help="Path to the experiment YAML file.")
    args = parser.parse_args()
    
    engine = MatrixEngine(args.config)
    asyncio.run(engine.run())