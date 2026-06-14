"""
run_pipeline.py
OrderFlow Analytics Pipeline — Full Pipeline Runner

Runs all layers in order:
  1. Bronze  — ingest raw CSVs
  2. Silver  — clean and standardize
  3. Quality — run data quality checks
  4. Gold    — build reporting tables

Run:
    python run_pipeline.py
"""

import time
from datetime import datetime

def log(msg):
    print(msg)

def run_step(name, module_path):
    log(f"\n{'='*55}")
    log(f"  STEP: {name}")
    log(f"{'='*55}")
    start = time.time()
    import importlib.util, sys
    spec   = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    log(f"\n  ✓ {name} completed in {round(time.time()-start, 2)}s")

if __name__ == "__main__":
    log("\n" + "★"*55)
    log("  OrderFlow Analytics Pipeline — Full Run")
    log(f"  Started: {datetime.now()}")
    log("★"*55)

    total_start = time.time()

    run_step("Bronze",          "bronze.py")
    run_step("Silver",          "silver.py")
    run_step("Quality Checks",  "quality_checks.py")
    run_step("Gold",            "gold.py")

    log("\n" + "★"*55)
    log(f"  Pipeline complete in {round(time.time()-total_start, 2)}s")
    log(f"  Finished: {datetime.now()}")
    log("★"*55 + "\n")
