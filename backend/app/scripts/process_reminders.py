#!/usr/bin/env python3
"""
CLI entry point to process automatic J-7 and J-2 reminders for GVG events.
Can be invoked via cron job or systemd timer, e.g.:
  python -m app.scripts.process_reminders
  python -m app.scripts.process_reminders --event-id <UUID> --reminder-type j7
"""

import argparse
import logging
import sys
import uuid

from app.core.database import SessionLocal
from app.services import reminder_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gvg.reminders_cli")


def main() -> int:
    parser = argparse.ArgumentParser(description="Process scheduled J-7 / J-2 reminders for GVG events.")
    parser.add_argument("--event-id", type=str, default=None, help="Target specific event ID (optional).")
    parser.add_argument("--reminder-type", type=str, choices=["j7", "j2"], default=None, help="Target reminder type (j7 or j2).")
    parser.add_argument("--force", action="store_true", help="Bypass idempotency check and resend.")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.event_id:
            try:
                ev_uuid = uuid.UUID(args.event_id)
            except ValueError:
                logger.error("Invalid UUID format: %s", args.event_id)
                return 1

            logger.info("Processing reminders for event %s (type=%s, force=%s)", ev_uuid, args.reminder_type, args.force)
            report = reminder_service.process_event_reminders(
                event_id=ev_uuid,
                reminder_type=args.reminder_type,
                force=args.force,
                db=db,
            )
            logger.info(
                "Event %s report: processed=%d sent=%d skipped=%d no_email=%d errors=%s",
                report.event_title,
                report.orders_processed,
                report.reminders_sent,
                report.reminders_skipped,
                report.orders_without_email,
                report.errors,
            )
            if report.errors:
                return 1
        else:
            logger.info("Processing all scheduled reminders across upcoming published events...")
            summary = reminder_service.process_all_scheduled_reminders(db=db)
            logger.info(
                "System run complete: events_evaluated=%d total_sent=%d total_skipped=%d",
                summary.events_evaluated,
                summary.total_reminders_sent,
                summary.total_reminders_skipped,
            )
            has_errors = any(rep.errors for rep in summary.reports)
            if has_errors:
                return 1
        return 0
    except Exception as ex:
        logger.exception("Fatal error during reminders processing: %s", ex)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
