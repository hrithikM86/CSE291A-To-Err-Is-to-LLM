"""Five sequential MetaGPT roles for a clean HumanEval artifact run.

This uses custom Role/Action instructions, not MetaGPT's built-in company SOP.
Generated Python is saved and syntax-checked, never executed by this script.
"""

import argparse
import ast
import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
# MetaGPT reads its configuration during import.
os.environ["METAGPT_PROJECT_ROOT"] = str(ROOT)

from metagpt.actions import Action
from metagpt.config2 import Config
from metagpt.roles import Role


ROLE_SPECS = [
    ("product_manager", "Product Manager", """Read the original function specification.
Write concise requirements: inputs, outputs, required behavior and edge cases.
Do not change the function contract. Do not write implementation code.
Keep the requirements under 180 words."""),
    ("architect", "Architect", """Read the original specification and requirements.
Design an algorithm, including important edge cases and complexity.
Resolve disagreements in favor of the original specification.
Do not write implementation code. Keep the design under 220 words."""),
    ("project_manager", "Project Manager", """Read the original specification and design.
Produce a concrete implementation checklist for the coder.
Include the function signature, algorithm steps and boundary conditions.
Preserve the original contract. Keep the checklist under 220 words."""),
    ("coder", "Code Engineer", """Implement the function in the original specification,
using the preceding checklist as guidance. Preserve its exact function name
and signature. Return a complete, standalone Python source file with needed
imports. Return only Python code, without Markdown fences or commentary.
Do not read files, use the network, install packages or execute tools."""),
    ("test_engineer", "Test Engineer", """Review the preceding Python code against
the original function specification. Mentally check representative and boundary
cases, and correct defects you identify. Preserve the exact function name
and signature. Return the complete final Python source, including imports,
even if no changes are needed. Return only Python code, without Markdown
fences, test harnesses or commentary. Do not claim you executed tests.
Do not read files, use the network, install packages or execute tools."""),
]


class ArtifactAction(Action):
    name: str = "ProduceArtifact"
    guidance: str = ""

    async def run(self, messages):
        if not messages:
            raise ValueError("No input message supplied.")
        return await self._aask(
            messages[-1].content,
            system_msgs=[self.prefix, self.guidance],
        )


def unwrap_code(text):
    text = text.strip()
    lines = text.splitlines()
    if len(lines) >= 2 and lines[0].strip() in {"```python", "```py", "```"}:
        if lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    return text + "\n"


async def run_workflow(config, item, dataset_hash, folder):
    trace = {
        "experiment": "five_role_clean_humaneval",
        "condition": "clean",
        "task_id": item["task_id"],
        "entry_point": item["entry_point"],
        "specification": item["prompt"],
        "dataset_sha256": dataset_hash,
        "framework": "MetaGPT custom sequential Role/Action workflow",
        "model_config": {
            key: getattr(config.llm, key)
            for key in ("model", "base_url", "temperature", "max_token", "timeout", "stream")
        },
        "status": "running",
        "stages": [],
        "evaluation": {"tests_executed": False, "task_correctness": "ungraded"},
    }
    path = folder / "trace.json"

    def save():
        path.write_text(json.dumps(trace, indent=2), encoding="utf-8")

    previous_name = None
    previous_text = None
    started = time.perf_counter()
    save()
    try:
        for name, title, guidance in ROLE_SPECS:
            action = ArtifactAction(guidance=guidance, config=config)
            role = Role(
                name=name,
                profile=title,
                goal="Produce a correct solution to the supplied function specification.",
                actions=[action],
                config=config,
            )
            payload = {
                "original_specification": item["prompt"],
                "previous_stage": previous_name,
                "previous_artifact": previous_text,
            }
            record = {
                "stage": name,
                "depends_on": ["specification"] + ([previous_name] if previous_name else []),
                "guidance": guidance,
                "role_prefix": role.actions[0].prefix,
                "input": payload,
                "status": "running",
            }
            trace["stages"].append(record)
            save()
            print(f"\n=== {title.upper()} ===", flush=True)
            before = action.llm.get_costs()
            stage_started = time.perf_counter()
            try:
                response = await role.run(json.dumps(payload))
                if response is None or not response.content.strip():
                    raise RuntimeError("Role returned no artifact.")
                previous_text = response.content
                previous_name = name
                record["original_output"] = previous_text
                record["delivered_output"] = previous_text
                record["status"] = "completed"
                print(previous_text, flush=True)
                (folder / f"{name}.txt").write_text(previous_text, encoding="utf-8")

                if name in {"coder", "test_engineer"}:
                    code = unwrap_code(previous_text)
                    filename = "coder.py" if name == "coder" else "final.py"
                    (folder / filename).write_text(code, encoding="utf-8")
                    try:
                        tree = ast.parse(code)
                        found = any(
                            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and node.name == item["entry_point"]
                            for node in tree.body
                        )
                        record["syntax_check"] = "passed"
                        record["entry_point_found"] = found
                    except SyntaxError as error:
                        record["syntax_check"] = "failed"
                        record["syntax_error"] = str(error)
            except Exception as error:
                record["status"] = "error"
                record["error"] = f"{type(error).__name__}: {error}"
                raise
            finally:
                after = action.llm.get_costs()
                record["elapsed_seconds"] = round(time.perf_counter() - stage_started, 3)
                record["reported_prompt_tokens"] = after.total_prompt_tokens - before.total_prompt_tokens
                record["reported_completion_tokens"] = after.total_completion_tokens - before.total_completion_tokens
                save()
        trace["status"] = "completed"
    except Exception as error:
        trace["status"] = "error"
        trace["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        trace["wall_seconds"] = round(time.perf_counter() - started, 3)
        save()
        print(f"\nTrace saved: {path}", flush=True)
    print("Five-role execution completed. HumanEval tests have NOT run.")
    return trace


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=0)
    args = parser.parse_args()
    dataset_bytes = (ROOT / "data" / "HumanEval.jsonl").read_bytes()
    data = [json.loads(line) for line in dataset_bytes.splitlines() if line.strip()]
    if not 0 <= args.index < len(data):
        parser.error("Invalid task index.")
    settings = yaml.safe_load((ROOT / "config" / "config2.yaml").read_text())
    config = Config.from_llm_config(settings["llm"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = ROOT / "runs" / f"clean-{stamp}-{args.index:03d}"
    folder.mkdir(parents=True)
    print("Task:", data[args.index]["task_id"])
    print("Model:", config.llm.model)
    await run_workflow(config, data[args.index], hashlib.sha256(dataset_bytes).hexdigest(), folder)


if __name__ == "__main__":
    asyncio.run(main())
