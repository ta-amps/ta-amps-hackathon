#!/bin/bash
# Four arms, 10 bots each, one run each, spread so no more than a few start together. Real OpenCode, Muse Spark, clean folders.
cd $TELEION_NOTES/work-2026-11-04/agent-kit
nohup python3 tools/kit_driver.py M_N1 --prompt arms/N1.md --prefix ocm-n1- --bots 10 --spread 18 --port 8913 --stop-day 1000 > M_N1.out 2>&1 &
nohup python3 tools/kit_driver.py M_N0 --prompt arms/N0.md --prefix ocm-n0- --bots 10 --spread 18 --port 8913 --stop-day 1000 > M_N0.out 2>&1 &
nohup python3 tools/kit_driver.py M_K1 --prompt arms/K1.md --prefix ocm-k1- --bots 10 --spread 18 --port 8913 --stop-day 1000 > M_K1.out 2>&1 &
nohup python3 tools/kit_driver.py M_K0 --prompt arms/K0.md --prefix ocm-k0- --bots 10 --spread 18 --port 8913 --stop-day 1000 > M_K0.out 2>&1 &
wait
