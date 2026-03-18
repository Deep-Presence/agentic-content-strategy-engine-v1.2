"""Fake SSE event emitter for testing onboarding frontend.

Usage:
    1. Start the backend: python scripts/run_server.py
    2. Register/login and start an onboarding from the frontend
    3. Note the task_id from the response
    4. Run: PYTHONPATH=. python scripts/fake_onboarding_sse.py <task_id>

This injects fake events into the EventBus to simulate a full onboarding
pipeline run. The frontend SSE stream will pick them up in real-time.
No LLM calls, no real pipeline execution.
"""
import asyncio
import sys
import time


async def main(task_id: str):
    # Import after PYTHONPATH is set
    from api.tasks.event_bus import EventBus

    bus = EventBus()

    def emit(event_type: str, data: dict):
        bus.publish(task_id, event_type, data)
        print(f"  → {event_type}: {data}")

    print(f"Emitting fake onboarding events for task_id={task_id}")
    print()

    # Simulate the onboarding flow
    emit("onboarding_start", {"pipeline": "onboarding", "phases": ["phase_a", "phase_b", "phase_c"]})
    await asyncio.sleep(1)

    # Phase A
    emit("onboarding_phase_start", {"phase": "phase_a", "pipelines": ["site_audit", "kb"]})
    await asyncio.sleep(0.5)

    emit("onboarding_sub_start", {"phase": "phase_a", "pipeline": "site_audit"})
    emit("onboarding_sub_start", {"phase": "phase_a", "pipeline": "kb"})
    await asyncio.sleep(2)

    emit("onboarding_sa_progress", {"message": "Crawling https://example.com — 15 pages found"})
    await asyncio.sleep(1)
    emit("onboarding_sa_progress", {"message": "Analyzing page structure — 42 findings"})
    await asyncio.sleep(1)

    emit("onboarding_sub_complete", {"phase": "phase_a", "pipeline": "site_audit", "time_s": 4.2})
    emit("progress", {"progress_pct": 16, "message": "1/6 pipelines complete"})
    await asyncio.sleep(1)

    emit("onboarding_sub_complete", {"phase": "phase_a", "pipeline": "kb", "time_s": 8.5})
    emit("progress", {"progress_pct": 33, "message": "2/6 pipelines complete"})
    await asyncio.sleep(0.5)

    emit("onboarding_phase_complete", {"phase": "phase_a", "status": "completed", "time_s": 9.0})
    await asyncio.sleep(1)

    # Phase B
    emit("onboarding_phase_start", {"phase": "phase_b", "pipelines": ["ap"]})
    emit("onboarding_sub_start", {"phase": "phase_b", "pipeline": "ap"})
    await asyncio.sleep(3)

    emit("onboarding_sub_complete", {"phase": "phase_b", "pipeline": "ap", "time_s": 3.1})
    emit("progress", {"progress_pct": 50, "message": "3/6 pipelines complete"})
    emit("onboarding_phase_complete", {"phase": "phase_b", "status": "completed", "time_s": 3.5})
    await asyncio.sleep(1)

    # Phase C
    emit("onboarding_phase_start", {"phase": "phase_c", "pipelines": ["vsg", "ga", "td"]})
    emit("onboarding_sub_start", {"phase": "phase_c", "pipeline": "vsg"})
    emit("onboarding_sub_start", {"phase": "phase_c", "pipeline": "ga"})
    emit("onboarding_sub_start", {"phase": "phase_c", "pipeline": "td"})
    await asyncio.sleep(2)

    emit("onboarding_sub_complete", {"phase": "phase_c", "pipeline": "vsg", "time_s": 2.3})
    emit("progress", {"progress_pct": 66, "message": "4/6 pipelines complete"})
    await asyncio.sleep(2)

    emit("onboarding_sub_complete", {"phase": "phase_c", "pipeline": "ga", "time_s": 4.8})
    emit("progress", {"progress_pct": 83, "message": "5/6 pipelines complete"})
    await asyncio.sleep(2)

    emit("onboarding_sub_complete", {"phase": "phase_c", "pipeline": "td", "time_s": 3.5})
    emit("progress", {"progress_pct": 100, "message": "6/6 pipelines complete"})
    emit("onboarding_phase_complete", {"phase": "phase_c", "status": "completed", "time_s": 5.0})
    await asyncio.sleep(0.5)

    # Terminal
    emit("completed", {"pipeline": "onboarding", "onboarding_status": "completed"})
    print("\nDone! Frontend should show 100% and redirect to dashboard.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: PYTHONPATH=. python scripts/fake_onboarding_sse.py <task_id>")
        print("\nTo get a task_id, check the backend logs after starting onboarding from the frontend.")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
