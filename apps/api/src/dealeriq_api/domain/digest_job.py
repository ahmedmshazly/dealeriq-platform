"""Daily digest email job (FR-064): summarizes each user's new/open alerts as a rendered-HTML
email, sent via stdlib `smtplib` to the MailHog container already running for local dev
(`infra/docker-compose.yml`) — no third-party email API, no templating-library dependency (the
content is a short, fixed-shape list of alert lines, not complex enough to justify one).

A user with zero un-emailed, non-resolved notifications gets no email at all — an empty digest
is not sent (spec.md User Story 3, Acceptance Scenario 2).
"""

import importlib.metadata
import smtplib
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from dealeriq_api.core.config import get_settings
from dealeriq_api.domain.job_lifecycle import begin_run
from dealeriq_api.domain.models.alerts import Alert, AlertStatus, Notification
from dealeriq_api.domain.models.analytics import AnalyticsRun, RunStatus
from dealeriq_api.domain.models.rbac import User

JOB_NAME = "digest"


def _code_version() -> str:
    try:
        return importlib.metadata.version("dealeriq-api")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _render_digest_html(user: User, alerts: list[Alert]) -> str:
    rows = "".join(
        f"<li><strong>{escape(a.severity.value.upper())}</strong> "
        f"[{escape(a.rule_key)}] — {escape(str(a.payload))}</li>"
        for a in alerts
    )
    return (
        f"<html><body>"
        f"<h2>DealerIQ daily alert digest</h2>"
        f"<p>Hi {escape(user.email)}, you have {len(alerts)} new/open alert(s):</p>"
        f"<ul>{rows}</ul>"
        f"</body></html>"
    )


def _send_email(to_address: str, html_body: str) -> None:
    settings = get_settings()
    message = MIMEMultipart("alternative")
    message["Subject"] = "DealerIQ: your daily alert digest"
    message["From"] = settings.smtp_from_address
    message["To"] = to_address
    message.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.send_message(message)


def run_digest_job(db: Session) -> AnalyticsRun:
    run = begin_run(db, job_name=JOB_NAME, code_version=_code_version())

    try:
        summary = _execute_pipeline(db)
        run.status = RunStatus.SUCCEEDED
        run.finished_at = datetime.now(UTC)
        run.metrics = summary
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.metrics = {"error": str(exc)}
        db.commit()
        raise

    db.commit()
    db.refresh(run)
    return run


def _execute_pipeline(db: Session) -> dict[str, int]:
    pending = db.execute(
        select(Notification, Alert, User)
        .join(Alert, Alert.id == Notification.alert_id)
        .join(User, User.id == Notification.user_id)
        .where(Notification.emailed_at.is_(None), Alert.status != AlertStatus.RESOLVED)
    ).all()

    by_user: dict[str, tuple[User, list[Notification], list[Alert]]] = {}
    for notification, alert, user in pending:
        key = str(user.id)
        if key not in by_user:
            by_user[key] = (user, [], [])
        by_user[key][1].append(notification)
        by_user[key][2].append(alert)

    emails_sent = 0
    now = datetime.now(UTC)
    for user, notifications, alerts in by_user.values():
        _send_email(user.email, _render_digest_html(user, alerts))
        for notification in notifications:
            notification.emailed_at = now
        emails_sent += 1

    return {"emails_sent": emails_sent, "users_with_pending_notifications": len(by_user)}
