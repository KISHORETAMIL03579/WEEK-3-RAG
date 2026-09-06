# week6/judge.py — LLM Judge Evaluator for HR Policy Answers

import os
import json
import re
import pathlib
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, List

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.1:8b")


def call_llm_judge(prompt: str, timeout: int = 45) -> str:
    """Calls Ollama API with the formatted judge prompt."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.1,
            "num_predict": 10
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json.get("response", "").strip()
    except Exception as e:
        # Fallback or error reporting
        return f"ERROR: {e}"


def parse_judge_output(output_str: str) -> int:
    """Parses judge output into binary 1 or 0."""
    clean = output_str.strip()
    match = re.search(r"\b([01])\b", clean)
    if match:
        return int(match.group(1))
    if "1" in clean:
        return 1
    if "0" in clean:
        return 0
    return 0


def evaluate_case_with_judge(case: Dict[str, Any], prompt_template: str) -> Tuple[int, str]:
    """Evaluates a single case with the provided judge prompt template."""
    formatted_prompt = prompt_template.format(
        question=case.get("question", ""),
        context=case.get("retrieved_context", ""),
        answer=case.get("answer", "")
    )
    raw_output = call_llm_judge(formatted_prompt)
    verdict = parse_judge_output(raw_output)
    return verdict, raw_output


def run_judge_suite(cases: List[Dict[str, Any]], prompt_path: str, labels: Dict[str, int]) -> Dict[str, Any]:
    """Runs the complete judge evaluation over the given cases and computes agreement."""
    prompt_template = pathlib.Path(prompt_path).read_text(encoding="utf-8")
    
    results = []
    agreements = 0
    human_correct = 0
    human_incorrect = 0
    judge_correct = 0
    judge_incorrect = 0
    disagreements = []

    for case in cases:
        cid = case["case_id"]
        expected_human = labels.get(cid, 1)
        if expected_human == 1:
            human_correct += 1
        else:
            human_incorrect += 1

        judge_verdict, raw_resp = evaluate_case_with_judge(case, prompt_template)
        
        if judge_verdict == 1:
            judge_correct += 1
        else:
            judge_incorrect += 1

        is_agreed = (judge_verdict == expected_human)
        if is_agreed:
            agreements += 1
        else:
            disagreements.append({
                "case_id": cid,
                "trace_id": case.get("trace_id"),
                "question": case.get("question"),
                "answer": case.get("answer"),
                "retrieved_context": case.get("retrieved_context"),
                "human_label": expected_human,
                "judge_label": judge_verdict,
                "raw_response": raw_resp,
                "taxonomy_mode": case.get("taxonomy_mode")
            })

        results.append({
            "case_id": cid,
            "trace_id": case.get("trace_id"),
            "question": case.get("question"),
            "human_label": expected_human,
            "judge_label": judge_verdict,
            "agreed": is_agreed,
            "raw_response": raw_resp,
            "taxonomy_mode": case.get("taxonomy_mode")
        })

    total = len(cases)
    agreement_pct = (agreements / total * 100.0) if total > 0 else 0.0

    return {
        "total_cases": total,
        "human_correct": human_correct,
        "human_incorrect": human_incorrect,
        "judge_correct": judge_correct,
        "judge_incorrect": judge_incorrect,
        "agreements": agreements,
        "agreement_pct": agreement_pct,
        "disagreements": disagreements,
        "results": results
    }
