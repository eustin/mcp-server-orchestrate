from typing import Any


class DAGScheduler:
    @staticmethod
    def build_execution_batches(tasks: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        if not tasks:
            return []

        file_to_tasks: dict[str, list[dict[str, Any]]] = {}
        for t in tasks:
            target = t.get("target")
            if target:
                file_to_tasks.setdefault(target, []).append(t)

        for colliding_tasks in file_to_tasks.values():
            if len(colliding_tasks) > 1:
                for idx, task in enumerate(colliding_tasks):
                    if idx > 0:
                        prev_id = colliding_tasks[idx - 1].get("id")
                        if prev_id:
                            if "blocked_by" not in task or task["blocked_by"] is None:
                                task["blocked_by"] = []
                            if prev_id not in task["blocked_by"]:
                                task["blocked_by"].append(prev_id)

        batches: list[list[dict[str, Any]]] = []
        remaining = list(tasks)
        completed_ids: set[str] = set()

        while remaining:
            current_batch: list[dict[str, Any]] = []
            next_remaining: list[dict[str, Any]] = []

            for task in remaining:
                blocked_by = task.get("blocked_by") or []
                if all(dep_id in completed_ids for dep_id in blocked_by):
                    current_batch.append(task)
                else:
                    next_remaining.append(task)

            if not current_batch:
                current_batch.append(next_remaining.pop(0))

            batches.append(current_batch)
            for task in current_batch:
                task_id = task.get("id")
                if task_id:
                    completed_ids.add(str(task_id))

            remaining = next_remaining

        return batches
