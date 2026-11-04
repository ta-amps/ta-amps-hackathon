#!/usr/bin/env python3
"""A second full reading of this comparison's refused outputs only, with the audit's fixed read of what each worker sent. First verdicts stay on record."""
import json
from warm_agent.audit_no_key import RECHECK_SQL, SAME_SUBMIT_SQL, d1_rows, group_by_object, recheck
from warm_agent.agent_loop import WarmServerAgent
from warm_agent.grid_config import load_warm_agent_grid
agent = WarmServerAgent(load_warm_agent_grid(), loopback_port_override=0)
agent.ensure_isolated_principals()
agent.ops["audit_recheck_tasks_file"] = __import__('os').environ['TELEION_NOTES'] + "/work-2026-11-04/agent-kit/audit-recheck-tasks.json"
rows = [r for r in d1_rows(RECHECK_SQL) if "_ocm-" in str(r["k"])]
print(len(rows), flush=True)
print(json.dumps(recheck(agent, rows, group_by_object(d1_rows(SAME_SUBMIT_SQL)), pause=float(agent.ops["audit_pause_seconds"]))))
