"""Optional single-process scheduler for local always-on deployments."""

from .config import get_settings
from .tasks.discover import discover


def start_scheduler():
    settings = get_settings()
    if not settings.enable_scheduler:
        return None
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(timezone=settings.timezone)
    scheduler.add_job(
        discover,
        CronTrigger(hour=settings.daily_run_hour, minute=0, timezone=settings.timezone),
        id="daily-discovery",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
