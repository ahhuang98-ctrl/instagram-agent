from typing import Callable

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from agent.logger import get_logger

logger = get_logger("scheduler")


def build_scheduler(
    job_func: Callable, config_path: str = "config.yaml"
) -> BlockingScheduler:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sched_cfg = config["schedule"]
    mode = sched_cfg["mode"]
    scheduler = BlockingScheduler()

    if mode == "cron":
        cron_cfg = sched_cfg["cron"]
        trigger = CronTrigger(
            hour=cron_cfg.get("hour", "*"),
            minute=cron_cfg.get("minute", "0"),
            second=cron_cfg.get("second", "0"),
            timezone=cron_cfg.get("timezone", "UTC"),
        )
        logger.info(
            f"Cron schedule: hour={cron_cfg.get('hour')} "
            f"minute={cron_cfg.get('minute')} tz={cron_cfg.get('timezone')}"
        )
    elif mode == "interval":
        interval_cfg = sched_cfg["interval"]
        trigger = IntervalTrigger(
            hours=interval_cfg.get("hours", 0),
            minutes=interval_cfg.get("minutes", 0),
        )
        logger.info(f"Interval schedule: {interval_cfg}")
    else:
        raise ValueError(f"Unknown schedule mode '{mode}'. Use 'cron' or 'interval'.")

    scheduler.add_job(
        job_func,
        trigger=trigger,
        id="instagram_post_job",
        name="Instagram AI Post Job",
        replace_existing=True,
        misfire_grace_time=300,
    )
    return scheduler
