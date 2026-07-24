import asyncio
import time
from backend.app.academy.agent_registry import AgentRegistryService
from backend.app.academy.schemas import CareerEntry
import os
import shutil

async def run_benchmark():
    if os.path.exists("backend/data/academy"):
        shutil.rmtree("backend/data/academy")

    service = AgentRegistryService()

    entry = CareerEntry(
        scout_name="ui-agent-1",
        event_type="test_event",
        details={"test": "data"}
    )

    await service.log_career_event(entry, save_registry=False, write_log=True)

    start = time.perf_counter()
    # Batch the tasks to prevent "Too many open files"
    for i in range(20):
        tasks = [service.log_career_event(entry, save_registry=False, write_log=True) for _ in range(100)]
        await asyncio.gather(*tasks)
    end = time.perf_counter()

    print(f"Time for 2000 logs: {end - start:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
