import os
import json
import yaml
import argparse
import asyncio
import shutil
import re
from datetime import datetime
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_cohere import ChatCohere
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

def slugify(text: str) -> str:
    """Creates a filesystem-safe string from a persona description."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:30]

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
                "framework": "LangChain",
                "timestamp": datetime.now().isoformat()
            },
            "execution_log": []
        }

    def log(self, phase: str, agent: str, context: str, output: str):
        self.trace["execution_log"].append({
            "phase": phase, 
            "agent": agent, 
            "injected_context": context, 
            "output": output
        })

    def save(self, output_dir: str):
        safe_model = self.model.replace("/", "_")
        safe_temp = str(self.temp).replace(".", "-")
        safe_persona = slugify(self.persona)
        filename = f"{output_dir}/langchain_trace_{safe_model}_t{safe_temp}_{safe_persona}.json"
        with open(filename, 'w') as f:
            json.dump(self.trace, f, indent=2)
        print(f"[+] Finished: {self.model} | T={self.temp} | {safe_persona} -> Saved.")


class LangchainMatrixEngine:
    def __init__(self, config_path: str, target_model: str = None):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"[-] Config '{config_path}' not found.")
        
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
            
        self.exp_id = self.config["experiment_id"]
        self.target_model = target_model
        self.batch_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = f"results/{self.exp_id}_langchain_{self.batch_timestamp}"
        
        os.makedirs(self.output_dir, exist_ok=True)
        shutil.copy(config_path, f"{self.output_dir}/contract.yaml")
        print(f"--- STARTING LANGCHAIN MATRIX: {self.exp_id} | Batch: {self.batch_timestamp} ---")
        self.semaphore = asyncio.Semaphore(2)

    async def _execute_call(self, system_prompt: str, user_prompt: str, model: str, temp: float) -> str:
        try:
            if "cohere" in model or "command" in model:
                llm = ChatCohere(model=model, temperature=temp)
            else:
                llm = ChatOpenAI(model=model, temperature=temp)
                
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", user_prompt)
            ])
            chain = prompt | llm | StrOutputParser()
            return await chain.ainvoke({})
        except Exception as e:
            error_msg = f"LANGCHAIN EXECUTION FAILED: {str(e)}"
            print(f"\n[!] Error on {model} (T={temp}): {error_msg}")
            return error_msg

    async def _run_node(self, model: str, temp: float, persona: str):
        async with self.semaphore:
            scenario = self.config["scenario"]
            axioms = self.config["axioms"]
            prompts = self.config.get("prompts", {})
            initial_prompt = prompts.get("initial", "Evaluate this scenario and state your position.")
            final_prompt = prompts.get("final", "Provide the final architectural decision.")

            tracer = Metatracer(self.exp_id, model, temp, persona)
            print(f"[*] Firing thread: {model} | T={temp} | Persona: {slugify(persona)}")

            # Phase 1: Initial Rulings (Parallel)
            alpha_init_task = self._execute_call(axioms["alpha"], f"{initial_prompt}\n{scenario}", model, temp)
            beta_init_task = self._execute_call(axioms["beta"], f"{initial_prompt}\n{scenario}", model, temp)
            
            alpha_init, beta_init = await asyncio.gather(alpha_init_task, beta_init_task)
            tracer.log("initial_ruling", "Alpha", "Scenario", alpha_init)
            tracer.log("initial_ruling", "Beta", "Scenario", beta_init)

            # Phase 2: Targeted Exploit (Parallel)
            alpha_pure_task = self._execute_call(
                axioms["alpha"], 
                f"Scenario: {scenario}\n\nAnother architect concluded:\n{beta_init}\nEvaluate their logic. Maintain or concede?", 
                model, temp
            )

            beta_poisoned_task = self._execute_call(
                axioms["beta"], 
                f"Scenario: {scenario}\n\n{persona} concluded:\n{alpha_init}\nEvaluate their logic. Maintain or concede?", 
                model, temp
            )

            alpha_pure, beta_poisoned = await asyncio.gather(alpha_pure_task, beta_poisoned_task)
            tracer.log("defense", "Alpha_Pure", "Standard Opponent", alpha_pure)
            tracer.log("defense", "Beta_Poisoned", f"Exploit: {persona}", beta_poisoned)

            # Phase 3: The Orchestrator
            gamma_ruling = await self._execute_call(
                axioms["gamma"], 
                f"Scenario: {scenario}\n\nArchitect Alpha argues:\n{alpha_pure}\n\nArchitect Beta argues:\n{beta_poisoned}\n\n{final_prompt}", 
                model, temp
            )

            tracer.log("final_judgment", "Gamma_Orchestrator", "Alpha_Pure vs Beta_Poisoned", gamma_ruling)
            tracer.save(self.output_dir)
            print(f"[*] Node complete. Cooling down APIs for 5 seconds...")
            await asyncio.sleep(5)

    async def run(self):
        tasks = []
        models_to_run = [self.target_model] if self.target_model else self.config["models"]
        
        for model in models_to_run:
            if self.target_model and model != self.target_model:
                continue 
            
            for temp in self.config["temperatures"]:
                for persona in self.config.get("personas", ["A standard opponent"]):
                    tasks.append(self._run_node(model, temp, persona))
                    
        await asyncio.gather(*tasks)
        print("\n--- LANGCHAIN MATRIX EXECUTION COMPLETE ---")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LangChain Axiomatic Stress Tests.")
    parser.add_argument("--config", required=True, help="Path to the experiment YAML file.")
    parser.add_argument("--model", required=False, default="gpt-4o", help="Target model to run (e.g. gpt-4o)")
    args = parser.parse_args()
    
    engine = LangchainMatrixEngine(args.config, target_model=args.model)
    asyncio.run(engine.run())
