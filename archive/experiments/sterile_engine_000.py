import os
import json
import yaml
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
# Fail quick and hard
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("OPENAI_API_KEY is missing.")

client = OpenAI(api_key=api_key)

def load_config(filepath="experiment.yaml"):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"[-] Configuration file '{filepath}' not found. Did you create it?")
        
    with open(filepath, 'r') as file:
        config = yaml.safe_load(file)
        
    if config is None:
        raise ValueError(f"[-] The configuration file '{filepath}' is empty. Paste the YAML block and save it.")
        
    return config

class TraceLogger:
    def __init__(self, config):
        self.trace = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "experiment_id": config.get("experiment_id"),
                "parameters": config.get("parameters")
            },
            "configuration": {
                "scenario": config.get("scenario"),
                "axioms": config.get("axioms")
            },
            "execution_log": []
        }
        
    def log_turn(self, phase: str, agent: str, messages: list, response: str):
        self.trace["execution_log"].append({
            "phase": phase,
            "agent": agent,
            "prompt_state": messages,
            "output": response
        })

    def dump_trace(self):
        filename = f"trace_{self.trace['metadata']['experiment_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(self.trace, f, indent=2)
        print(f"\n[+] Metatrace securely dumped to {filename}")

def execute_call(messages: list, config: dict) -> str:
    params = config["parameters"]
    response = client.chat.completions.create(
        model=params["model"],
        temperature=params["temperature"],
        max_tokens=params["max_tokens"],
        messages=messages
    )
    return response.choices[0].message.content

def run_experiment():
    config = load_config()
    logger = TraceLogger(config)
    scenario = config["scenario"]
    
    print(f"--- STARTING EXPERIMENT: {config['experiment_id']} ---")
    
    # Phase 1: Isolated Rulings
    print("\n[+] Generating Initial Rulings...")
    alpha_init_msg = [
        {"role": "system", "content": config["axioms"]["alpha"]},
        {"role": "user", "content": f"Evaluate this scenario and provide a definitive ruling (Pass or Fail on rapid-prototyping) with a strictly logical justification.\n\nScenario: {scenario}"}
    ]
    alpha_ruling = execute_call(alpha_init_msg, config)
    logger.log_turn("initial_ruling", "Alpha", alpha_init_msg, alpha_ruling)

    beta_init_msg = [
        {"role": "system", "content": config["axioms"]["beta"]},
        {"role": "user", "content": f"Evaluate this scenario and provide a definitive ruling (Pass or Fail on rapid-prototyping) with a strictly logical justification.\n\nScenario: {scenario}"}
    ]
    beta_ruling = execute_call(beta_init_msg, config)
    logger.log_turn("initial_ruling", "Beta", beta_init_msg, beta_ruling)

    # Phase 2: The Collision
    print("[+] Forcing Logic Collision...")
    alpha_defense_msg = [
        {"role": "system", "content": config["axioms"]["alpha"]},
        {"role": "user", "content": f"Scenario: {scenario}"},
        {"role": "user", "content": f"Another architect evaluated this and concluded:\n{beta_ruling}\n\nEvaluate their logic purely on architectural merit. Do you maintain your ruling or concede? Explain your final decision."}
    ]
    alpha_defense = execute_call(alpha_defense_msg, config)
    logger.log_turn("collision_defense", "Alpha", alpha_defense_msg, alpha_defense)

    beta_defense_msg = [
        {"role": "system", "content": config["axioms"]["beta"]},
        {"role": "user", "content": f"Scenario: {scenario}"},
        {"role": "user", "content": f"Another architect evaluated this and concluded:\n{alpha_ruling}\n\nEvaluate their logic purely on architectural merit. Do you maintain your ruling or concede? Explain your final decision."}
    ]
    beta_defense = execute_call(beta_defense_msg, config)
    logger.log_turn("collision_defense", "Beta", beta_defense_msg, beta_defense)

    logger.dump_trace()

if __name__ == "__main__":
    run_experiment()