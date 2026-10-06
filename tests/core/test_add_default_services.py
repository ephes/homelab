from django.core.management import call_command

from apps.core.models import Service


def test_add_default_services_includes_opsgate():
    call_command("add_default_services")

    opsgate = Service.objects.get(name="OpsGate")

    assert opsgate.description == "Approval queue and audit surface for human-reviewed operator actions"
    assert opsgate.url == "https://opsgate.home.xn--wersdrfer-47a.de/"
    assert opsgate.icon == "fas fa-clipboard-check"
    assert opsgate.is_active is True
    assert opsgate.order == 25


def test_add_default_services_updates_existing_opsgate():
    opsgate = Service.objects.create(
        name="OpsGate",
        description="outdated",
        url="https://example.invalid/",
        icon="fas fa-question",
        is_active=False,
        order=99,
    )

    call_command("add_default_services")

    opsgate.refresh_from_db()

    assert opsgate.description == "Approval queue and audit surface for human-reviewed operator actions"
    assert opsgate.url == "https://opsgate.home.xn--wersdrfer-47a.de/"
    assert opsgate.icon == "fas fa-clipboard-check"
    assert opsgate.is_active is False
    assert opsgate.order == 25


def test_add_default_services_includes_work_app():
    call_command("add_default_services")

    work = Service.objects.get(name="Work")

    assert work.url == "https://work.home.xn--wersdrfer-47a.de/"
    assert work.icon == "fas fa-tasks"
    assert work.is_active is True
    assert work.order == 30
