import json, sys, modal, time
kind = sys.argv[1]
if kind == "train":
    f = modal.Function.from_name("glimmer-pick-v2", "train")
    for v in sys.argv[2:]:
        c = f.spawn(v); print(v, c.object_id, flush=True); time.sleep(5)
