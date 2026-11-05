"""run_batch.py <tasks.json> <run> [--default]: spin up one worker per Task, at most 4 at a time."""
import concurrent.futures as cf,json,sys,time
from pathlib import Path
import work
tasks=json.load(open(sys.argv[1])); run=sys.argv[2]; cmp="--default" in sys.argv
sb=Path(__file__).resolve().parent/"sandbox.sh"
def one(t):
    t0=time.time()
    try:
        r=work.spin_up_task(t,run,sb,compare_default=cmp)
        a=r["assembly"]; o=r.get("outcome",{})
        print(json.dumps({"task":t["task_id"][-22:],"kind":t.get("category"),"harness":a["harness"],"model":a["model"],"tools":a["tools"],"skills":[s.get("id") for s in a["skills"]],"rules":len(a["rules"]),"usd_budget":a["budget"]["usd"],"pass":o.get("pass"),"people":o.get("needs_people"),"usd":o.get("usd"),"used":(r.get("made") or {}).get("tools_used"),"rule_fail":r.get("rule_failures"),"why":(r.get("read") or {}).get("why"),"submit":o.get("submit"),"default_pass":(r.get("default_arm") or {}).get("read",{}).get("pass"),"s":round(time.time()-t0)}),flush=True)
    except Exception as e:
        import traceback; print(json.dumps({"task":t["task_id"],"crash":traceback.format_exc()[-700:]}),flush=True)
with cf.ThreadPoolExecutor(4) as ex: list(ex.map(one,tasks))
print("done",flush=True)
