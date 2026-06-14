"""Notifier adapters and channel dispatch for Gotra reports."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
from typing import Any
from urllib import parse, request

from orchestrator.notifications.notifier import NotificationMessage, Notifier

from gotra.reporting_ext.reports import ReportSection
from gotra.reporting_ext.reports import ReportFiles, ReportType, write_report_files


class TelegramNotifier(Notifier):
    """Telegram Bot API notifier."""

    def __init__(
        self,
        *,
        bot_token: str | None = None,
        chat_id: str | None = None,
        api_base_url: str = "https://api.telegram.org",
        timeout: float = 10.0,
        opener: Callable[..., Any] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        env_map = os.environ if env is None else env
        self.bot_token = bot_token or _first_env(
            env_map,
            "GOTRA_TELEGRAM_BOT_TOKEN",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_TOKEN",
        )
        self.chat_id = chat_id or _first_env(
            env_map,
            "GOTRA_TELEGRAM_CHAT_ID",
            "TELEGRAM_CHAT_ID",
        )
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = timeout
        self.opener = opener or request.urlopen

    @property
    def available(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send(self, message: NotificationMessage) -> bool:
        if not self.available:
            return False

        payload = parse.urlencode(
            {
                "chat_id": self.chat_id,
                "text": _telegram_text(message),
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        telegram_request = request.Request(
            f"{self.api_base_url}/bot{self.bot_token}/sendMessage",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            response = self.opener(telegram_request, timeout=self.timeout)
            status = int(getattr(response, "status", getattr(response, "code", 200)))
            body = response.read() if hasattr(response, "read") else b""
            close = getattr(response, "close", None)
            if close is not None:
                close()
        except Exception:
            return False

        if status >= 400:
            return False
        if not body:
            return True
        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return True
        return decoded.get("ok", True) is not False


class SmtpNotifier(Notifier):
    """SMTP email notifier."""

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | str | None = None,
        username: str | None = None,
        password: str | None = None,
        from_addr: str | None = None,
        to_addrs: str | list[str] | tuple[str, ...] | None = None,
        use_tls: bool | str | None = None,
        use_ssl: bool | str | None = None,
        timeout: float = 10.0,
        smtp_factory: Callable[..., Any] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        env_map = os.environ if env is None else env
        self.host = host or _first_env(env_map, "GOTRA_SMTP_HOST", "SMTP_HOST", "SMTP_SERVER")
        self.use_ssl = _as_bool(
            use_ssl if use_ssl is not None else _first_env(env_map, "GOTRA_SMTP_USE_SSL", "SMTP_USE_SSL"),
            default=False,
        )
        self.port = int(
            port
            or _first_env(env_map, "GOTRA_SMTP_PORT", "SMTP_PORT")
            or (465 if self.use_ssl else 587)
        )
        self.username = username or _first_env(env_map, "GOTRA_SMTP_USERNAME", "SMTP_USERNAME")
        self.password = password or _first_env(env_map, "GOTRA_SMTP_PASSWORD", "SMTP_PASSWORD")
        self.from_addr = from_addr or _first_env(
            env_map,
            "GOTRA_SMTP_FROM",
            "SMTP_FROM",
            "SMTP_FROM_ADDR",
        )
        self.to_addrs = _split_addresses(
            to_addrs
            if to_addrs is not None
            else _first_env(env_map, "GOTRA_SMTP_TO", "SMTP_TO", "SMTP_RECIPIENTS")
        )
        self.use_tls = _as_bool(
            use_tls if use_tls is not None else _first_env(env_map, "GOTRA_SMTP_USE_TLS", "SMTP_USE_TLS"),
            default=not self.use_ssl,
        )
        self.timeout = timeout
        self.smtp_factory = smtp_factory

    @property
    def available(self) -> bool:
        return bool(self.host and self.from_addr and self.to_addrs)

    def send(self, message: NotificationMessage) -> bool:
        if not self.available:
            return False

        email = EmailMessage()
        email["Subject"] = message.title
        email["From"] = self.from_addr
        email["To"] = ", ".join(self.to_addrs)
        email.set_content(_email_text(message))
        for attachment in message.attachments:
            path = Path(attachment)
            if not path.exists() or not path.is_file():
                continue
            email.add_attachment(
                path.read_bytes(),
                maintype="application",
                subtype="octet-stream",
                filename=path.name,
            )

        try:
            smtp = self._open_smtp()
            with smtp as client:
                if self.use_tls and not self.use_ssl:
                    client.starttls()
                if self.username:
                    client.login(self.username, self.password or "")
                client.send_message(email)
        except Exception:
            return False
        return True

    def _open_smtp(self) -> Any:
        factory = self.smtp_factory or (smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP)
        try:
            return factory(self.host, self.port, timeout=self.timeout)
        except TypeError:
            return factory(self.host, self.port)


@dataclass(frozen=True)
class ChannelStatus:
    channel: str
    sent: bool
    attempted: bool
    error: str | None = None


@dataclass(frozen=True)
class ReportNotificationResult:
    report: ReportFiles
    statuses: tuple[ChannelStatus, ...]

    @property
    def ok(self) -> bool:
        return self.report.markdown_path.exists() and self.report.html_path.exists()

    @property
    def nonfatal(self) -> bool:
        return self.ok

    @property
    def degraded(self) -> bool:
        return any(not status.sent for status in self.statuses if status.channel != "local")


def parse_notifier_channels(
    value: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Parse NOTIFIER_CHANNELS into normalized, deduplicated channel names."""

    env_map = os.environ if env is None else env
    raw_value = value if value is not None else env_map.get("NOTIFIER_CHANNELS", "local")
    if raw_value is None:
        return ("local",)

    channels: list[str] = []
    for item in raw_value.replace(";", ",").split(","):
        normalized = item.strip().lower()
        if not normalized:
            continue
        if normalized in {"none", "off", "false", "disabled"}:
            return ()
        normalized = _normalize_channel_name(normalized)
        if normalized not in channels:
            channels.append(normalized)
    return tuple(channels or ["local"])


def publish_report(
    *,
    data_dir: str | Path = "data",
    report_date: str | date | datetime,
    report_type: ReportType,
    sections: Mapping[str, Any] | list[ReportSection | tuple[str, Any]] | None = None,
    channels: tuple[str, ...] | list[str] | None = None,
    notifiers: Mapping[str, Notifier] | None = None,
    env: Mapping[str, str] | None = None,
    title: str | None = None,
) -> ReportNotificationResult:
    """Write report files and notify selected channels without making failures fatal."""

    env_map = os.environ if env is None else env
    report = write_report_files(
        data_dir=data_dir,
        report_date=report_date,
        report_type=report_type,
        sections=sections,
        title=title,
    )
    selected_channels = tuple(channels) if channels is not None else parse_notifier_channels(env=env_map)
    message = NotificationMessage(
        title=title or f"Gotra {report.report_type.title()} Report - {report.report_date}",
        body=report.markdown,
        attachments=[report.markdown_path, report.html_path],
        priority="normal",
    )
    statuses = [
        _deliver_channel(channel, message=message, notifiers=notifiers or {}, env=env_map)
        for channel in selected_channels
    ]
    return ReportNotificationResult(report=report, statuses=tuple(statuses))


publish_daily_report = publish_report


def _deliver_channel(
    channel: str,
    *,
    message: NotificationMessage,
    notifiers: Mapping[str, Notifier],
    env: Mapping[str, str],
) -> ChannelStatus:
    normalized = _normalize_channel_name(channel.strip().lower()) if channel else "local"
    if normalized in {"none", "off", "false", "disabled"}:
        return ChannelStatus(channel=normalized, sent=True, attempted=False)
    if normalized == "local":
        return ChannelStatus(channel="local", sent=True, attempted=False)
    if normalized not in {"telegram", "smtp"}:
        return ChannelStatus(
            channel=normalized,
            sent=False,
            attempted=False,
            error=f"unsupported notifier channel: {normalized}",
        )

    notifier = notifiers.get(normalized) or _build_notifier(normalized, env=env)
    if hasattr(notifier, "available") and not bool(getattr(notifier, "available")):
        return ChannelStatus(
            channel=normalized,
            sent=False,
            attempted=False,
            error=f"{normalized} notifier unavailable",
        )
    try:
        sent = bool(notifier.send(message))
    except Exception as exc:
        return ChannelStatus(channel=normalized, sent=False, attempted=True, error=str(exc))
    if not sent:
        return ChannelStatus(channel=normalized, sent=False, attempted=True, error="send returned false")
    return ChannelStatus(channel=normalized, sent=True, attempted=True)


def _build_notifier(channel: str, *, env: Mapping[str, str]) -> Notifier:
    if channel == "telegram":
        return TelegramNotifier(env=env)
    if channel == "smtp":
        return SmtpNotifier(env=env)
    raise ValueError(f"unsupported notifier channel: {channel}")


def _normalize_channel_name(channel: str) -> str:
    return {
        "email": "smtp",
        "mail": "smtp",
        "file": "local",
        "report": "local",
        "reports": "local",
    }.get(channel, channel)


def _telegram_text(message: NotificationMessage) -> str:
    text = _message_text(message)
    if len(text) <= 3900:
        return text
    return f"{text[:3800].rstrip()}\n\n[truncated; see local report attachments]"


def _email_text(message: NotificationMessage) -> str:
    return _message_text(message)


def _message_text(message: NotificationMessage) -> str:
    parts = [message.title, "", message.body.strip()]
    if message.attachments:
        parts.extend(["", "Attachments:"])
        parts.extend(f"- {path}" for path in message.attachments)
    return "\n".join(parts).strip()


def _first_env(env: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return None


def _as_bool(value: bool | str | None, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_addresses(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_addresses = value.replace(";", ",").split(",")
    else:
        raw_addresses = list(value)
    return [address.strip() for address in raw_addresses if address.strip()]
