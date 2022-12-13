import psutil  # type: ignore
from anyio import to_thread
from fastapi import APIRouter, Depends  # type: ignore
from fps.hooks import register_router  # type: ignore
from fps_auth_base import User, current_user  # type: ignore

from .config import get_resource_usage_config

router = APIRouter()


@router.get("/api/metrics/v1")
async def get_content(
    user: User = Depends(current_user(permissions={"contents": ["read"]})),
    config=Depends(get_resource_usage_config),
):
    cur_process = psutil.Process()
    all_processes = [cur_process] + cur_process.children(recursive=True)

    # Get memory information
    rss = 0
    for p in all_processes:
        try:
            rss += p.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    mem_limit = config.mem_limit

    limits = {"memory": {"rss": mem_limit}}
    if config.mem_limit and config.mem_warning_threshold:
        limits["memory"]["warn"] = (mem_limit - rss) < (mem_limit * config.mem_warning_threshold)

    metrics = {"rss": rss, "limits": limits}

    # Optionally get CPU information
    if config.track_cpu_percent:
        cpu_count = psutil.cpu_count()
        cpu_percent = await to_thread.run_sync(_get_cpu_percent, all_processes)

        if config.cpu_limit:
            limits["cpu"] = {"cpu": config.cpu_limit}
            if config.cpu_warning_threshold:
                limits["cpu"]["warn"] = (config.cpu_limit - cpu_percent) < (
                    config.cpu_limit * config.cpu_warning_threshold
                )

        metrics.update(cpu_percent=cpu_percent, cpu_count=cpu_count)

    return metrics


def _get_cpu_percent(all_processes):
    def get_cpu_percent(p):
        try:
            return p.cpu_percent(interval=0.05)
        # Avoid littering logs with stack traces complaining
        # about dead processes having no CPU usage
        except BaseException:
            return 0

    return sum([get_cpu_percent(p) for p in all_processes])


r = register_router(router)
