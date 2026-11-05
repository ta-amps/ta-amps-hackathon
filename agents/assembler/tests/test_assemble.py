import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fp, spin_up

CODE = {"task_id": "a", "category": "ngo_public_good", "step_mode": "atomic_cognitive_step", "complexity_milli": 700, "title": "D6 fixture pair for the roster validator", "prompt": "Extend the validator with fixtures and a regression test, in python, with made-up rosters."}
CODE2 = {**CODE, "task_id": "b", "title": "D7 fixture pair for the roster validator", "prompt": "Extend the validator with fixtures and a regression test, in python, with made-up shift rosters."}
PROSE = {"task_id": "c", "category": "report_upkeep", "step_mode": "atomic_cognitive_step", "complexity_milli": 700, "title": "Plain language copy", "prompt": "Write a plain language sheet from https://example.org/report using claim ids such as (C2)."}
FIELD = {"task_id": "d", "category": "ngo_public_good", "step_mode": "atomic_cognitive_step", "complexity_milli": 800, "title": "Field team trial", "prompt": "A field team prints the card and runs the physical trial with gloved users."}


def row(task, harness, model, ok, people=False):
    return {"task_id": task["task_id"] + "-old", "fp": fp.fingerprint(task), "assembly": {"harness": harness, "model": model}, "outcome": {"pass": ok, "usd": 0.01, "needs_people": people}, "source": "test"}


def test_near_scores_above_different():
    assert fp.score(fp.fingerprint(CODE), fp.fingerprint(CODE2)) >= 0.72 > fp.score(fp.fingerprint(CODE), fp.fingerprint(PROSE))


def test_needs_read_from_text():
    assert "run_code" in fp.fingerprint(CODE)["needs"] and "people_or_hardware" in fp.fingerprint(FIELD)["needs"]


def test_default_when_nothing_is_known():
    got = spin_up.assemble(CODE, [])
    assert got["assembly"]["harness"] == "opencode" and "bash" in got["assembly"]["tools"] and got["fallback_default"]


def test_assemblies_differ_by_task():
    a, b, c = (spin_up.assemble(t, [])["assembly"] for t in (CODE, PROSE, FIELD))
    assert a["tools"] != b["tools"] and c["harness"] == "deterministic_only" and c["handler"] == "leave_open"
    assert "cites_claim_ids" in b["rules"] and "tests_pass_when_rerun_by_the_runner" in a["rules"]


def test_outcomes_change_a_later_assembly():
    bad = [row(CODE, "opencode", spin_up.SPARK, False) for _ in range(3)]
    good = [row(CODE, "opencode", spin_up.WONDER, True) for _ in range(3)]
    got = spin_up.assemble(CODE2, bad + good)
    assert got["assembly"]["model"] == spin_up.WONDER and got["changed_by_outcomes"]


def test_neighbors_who_needed_people_leave_a_task_open():
    got = spin_up.assemble(CODE2, [row(CODE, "json_answer", spin_up.SPARK, False, people=True) for _ in range(4)])
    assert got["assembly"]["handler"] == "leave_open" and got["changed_by_outcomes"]
