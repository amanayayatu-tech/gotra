from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib import parse

from orchestrator.notifications.notifier import NotificationMessage, Notifier

from gotra.reporting_ext import (
    SmtpNotifier,
    TelegramNotifier,
    parse_notifier_channels,
    publish_report,
    write_report_files,
)


def test_report_helper_writes_morning_markdown_and_html(tmp_path: Path) -> None:
    report = write_report_files(
        data_dir=tmp_path / "data",
        report_date="2026-06-14",
        report_type="morning",
        sections={
            "System Health": {"pipeline_failed": False, "skipped": False},
            "Research Signals": [{"ticker": "META", "status": "ready"}],
        },
    )

    assert report.markdown_path == tmp_path / "data" / "reports" / "2026-06-14_morning.md"
    assert report.html_path == tmp_path / "data" / "reports" / "2026-06-14_morning.html"
    markdown = report.markdown_path.read_text(encoding="utf-8")
    assert "## System Health" in markdown
    assert "- pipeline_failed: False" in markdown
    assert "## Research Signals" in markdown
    assert "## Judge Decisions" in markdown
    assert "## Active Predictions" in markdown
    assert "## Knowledge Additions" in markdown
    assert "## Outcome Updates" not in markdown
    assert "System Health" in report.html_path.read_text(encoding="utf-8")


def test_report_helper_adds_evening_only_sections(tmp_path: Path) -> None:
    report = write_report_files(
        data_dir=tmp_path / "data",
        report_date="20260614",
        report_type="evening",
        sections={"Auto-Quarantine": [{"knowledge_id": "K-1", "status": "quarantined"}]},
    )

    markdown = report.markdown_path.read_text(encoding="utf-8")
    assert report.markdown_path.name == "20260614_evening.md"
    assert "## Outcome Updates" in markdown
    assert "## Auto-Quarantine" in markdown
    assert "## Strong Pending Approval" in markdown
    assert "## Next Run Queue" in markdown
    assert "- knowledge_id: K-1, status: quarantined" in markdown


def test_parse_notifier_channels_normalizes_env(monkeypatch) -> None:
    monkeypatch.setenv("NOTIFIER_CHANNELS", "telegram, email, file, telegram")

    assert parse_notifier_channels() == ("telegram", "smtp", "local")


def test_publish_report_degrades_when_selected_channels_are_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("NOTIFIER_CHANNELS", "telegram,smtp")
    for key in (
        "GOTRA_TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "GOTRA_SMTP_HOST",
        "SMTP_HOST",
        "GOTRA_SMTP_TO",
        "SMTP_TO",
    ):
        monkeypatch.delenv(key, raising=False)

    result = publish_report(
        data_dir=tmp_path / "data",
        report_date="20260614",
        report_type="morning",
        sections={"System Health": "ok"},
    )

    assert result.ok is True
    assert result.nonfatal is True
    assert result.degraded is True
    assert [(status.channel, status.sent, status.attempted) for status in result.statuses] == [
        ("telegram", False, False),
        ("smtp", False, False),
    ]
    assert result.report.markdown_path.exists()
    assert result.report.html_path.exists()


def test_publish_report_uses_injected_fake_notifier(tmp_path: Path) -> None:
    fake = FakeNotifier()

    result = publish_report(
        data_dir=tmp_path / "data",
        report_date="20260614",
        report_type="evening",
        sections={"System Health": "ok"},
        channels=("telegram",),
        notifiers={"telegram": fake},
    )

    assert result.statuses[0].sent is True
    assert fake.messages[0].title == "Gotra Evening Report - 20260614"
    assert fake.messages[0].attachments == [result.report.markdown_path, result.report.html_path]


def test_telegram_notifier_uses_fake_opener_without_network() -> None:
    calls: list[Any] = []

    def fake_opener(request, timeout: float):
        calls.append((request, timeout))
        return FakeHttpResponse(b'{"ok": true}')

    sent = TelegramNotifier(
        bot_token="token-1",
        chat_id="chat-1",
        opener=fake_opener,
        timeout=1.5,
    ).send(NotificationMessage(title="Report", body="body", attachments=[Path("report.md")]))

    assert sent is True
    request, timeout = calls[0]
    assert timeout == 1.5
    assert request.full_url.endswith("/bottoken-1/sendMessage")
    payload = parse.parse_qs(request.data.decode("utf-8"))
    assert payload["chat_id"] == ["chat-1"]
    assert "Report" in payload["text"][0]
    assert "report.md" in payload["text"][0]


def test_smtp_notifier_uses_fake_factory_without_network(tmp_path: Path) -> None:
    attachment = tmp_path / "report.md"
    attachment.write_text("# report", encoding="utf-8")
    sent_messages: list[Any] = []

    def fake_factory(host: str, port: int, timeout: float):
        return FakeSmtp(host, port, timeout, sent_messages)

    sent = SmtpNotifier(
        host="smtp.example.com",
        port=2525,
        from_addr="gotra@example.com",
        to_addrs="ops@example.com",
        username="user",
        password="pass",
        smtp_factory=fake_factory,
    ).send(NotificationMessage(title="Report", body="body", attachments=[attachment]))

    assert sent is True
    message = sent_messages[0]
    assert message["Subject"] == "Report"
    assert message["From"] == "gotra@example.com"
    assert message["To"] == "ops@example.com"
    assert any(part.get_filename() == "report.md" for part in message.iter_attachments())


class FakeNotifier(Notifier):
    available = True

    def __init__(self) -> None:
        self.messages: list[NotificationMessage] = []

    def send(self, message: NotificationMessage) -> bool:
        self.messages.append(message)
        return True


class FakeHttpResponse:
    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.closed = False

    def read(self) -> bytes:
        return self.body

    def close(self) -> None:
        self.closed = True


class FakeSmtp:
    def __init__(
        self,
        host: str,
        port: int,
        timeout: float,
        sent_messages: list[Any],
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sent_messages = sent_messages
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message) -> None:
        self.sent_messages.append(message)
