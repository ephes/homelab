"""Historical operations must respect the migration connection and row ownership."""

import pytest
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

SEEDS = [
    ("0002_add_default_services", ["Home Assistant", "Nyxmon", "Unifi"]),
    ("0003_add_snappymail_service", ["SnappyMail"]),
    ("0004_add_postfixadmin_service", ["PostfixAdmin"]),
    ("0005_add_fractal_ipmi_service", ["Fractal IPMI"]),
    ("0006_add_cms_services", ["Family Blog CMS", "Python Podcast CMS"]),
    ("0007_add_qbittorrent_service", ["qBittorrent"]),
    ("0008_add_takahe_service", ["Takahe"]),
    ("0009_add_mastodon_service", ["Mastodon"]),
    ("0010_add_open_webui_service", ["Open WebUI"]),
    ("0012_add_openclaw_service", ["OpenClaw"]),
    ("0013_add_graphyard_and_grafana_services", ["Graphyard", "Grafana"]),
    ("0014_add_logyard_service", ["Logyard"]),
    ("0015_add_archive_service", ["Archive"]),
    ("0016_add_opsgate_service", ["OpsGate"]),
]
pytestmark = pytest.mark.django_db(transaction=True, databases=["default", "secondary"])


def migrate(alias, targets):
    executor = MigrationExecutor(connections[alias])
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps.get_model("core", "Service")


@pytest.fixture
def at_initial(django_db_use_migrations):
    assert django_db_use_migrations, "Run with --migrations --create-db --ds=database_tests.settings"
    for alias in ("default", "secondary"):
        model = migrate(alias, [("core", "0001_initial")])
        model.objects.using(alias).all().delete()
    yield
    for alias in ("default", "secondary"):
        executor = MigrationExecutor(connections[alias])
        executor.migrate(executor.loader.graph.leaf_nodes("core"))


def rows(model, alias):
    return list(model.objects.using(alias).order_by("pk").values())


def customize(model, alias, name):
    return model.objects.using(alias).update_or_create(
        name=name,
        defaults={
            "description": f"Synthetic owner on {alias}",
            "url": f"https://{alias}.example/custom/",
            "icon": "owner-icon",
            "logo_file": "services/logos/synthetic-owner.svg",
            "is_active": False,
            "order": 987,
        },
    )[0]


@pytest.mark.parametrize(("migration", "names"), SEEDS, ids=[seed[0] for seed in SEEDS])
@pytest.mark.parametrize("existing", [False, True], ids=["new-seeds", "owner-rows"])
def test_seed_forward_and_reverse_are_local_and_preserve_rows(at_initial, migration, names, existing):
    target = ("core", migration)
    executor = MigrationExecutor(connections["secondary"])
    parents = [node.key for node in executor.loader.graph.node_map[target].parents]
    model = migrate("secondary", parents)
    # Remove any rows retained by conservative reversals / prerequisite seeds.
    model.objects.using("secondary").filter(name__in=names).delete()
    customize(model, "secondary", "Unrelated secondary")
    for name in names:
        customize(model, "default", name)
        if existing:
            customize(model, "secondary", name)
    default_before = rows(model, "default")
    secondary_before = rows(model, "secondary")
    migrate("secondary", [target])
    assert rows(model, "default") == default_before
    after_forward = rows(model, "secondary")
    if existing:
        assert after_forward == secondary_before
    else:
        for name in names:
            seeded = model.objects.using("secondary").get(name=name)
            assert seeded.url and seeded.icon and seeded.is_active
        assert len(after_forward) == len(secondary_before) + len(names)
    migrate("secondary", parents)
    assert rows(model, "default") == default_before
    assert rows(model, "secondary") == after_forward  # No ownership was recorded: retain new seeds too.


def test_historical_webui_update_uses_secondary_connection(at_initial):
    before = [("core", "0010_add_open_webui_service")]
    model = migrate("secondary", before)
    for alias in ("default", "secondary"):
        customize(model, alias, "Open WebUI")
    default_before = rows(model, "default")
    migrate("secondary", [("core", "0011_update_open_webui_service")])
    assert rows(model, "default") == default_before
    service = model.objects.using("secondary").get(name="Open WebUI")
    assert service.url == "https://open-webui.home.xn--wersdrfer-47a.de/"
    assert service.is_active is True
    secondary_after = rows(model, "secondary")
    migrate("secondary", before)
    assert rows(model, "default") == default_before
    assert rows(model, "secondary") == secondary_after


MINIO_RETIRED = {
    "name": "MinIO",
    "description": "S3-compatible object storage for backups and data archiving",
    "url": "https://minio.home.xn--wersdrfer-47a.de/",
    "icon": "fas fa-database",
    "logo_file": "services/logos/minio.png",
    "is_active": True,
    "order": 8,
}
REPLACEMENT = ("core", "0018_replace_minio_with_rustfs")
BEFORE_REPLACEMENT = [("core", "0017_merge_20260505_1239")]


def replacement_fields():
    from importlib import import_module

    return import_module("apps.core.migrations.0018_replace_minio_with_rustfs").RUSTFS


def before_replacement():
    model = migrate("secondary", BEFORE_REPLACEMENT)
    for alias in ("default", "secondary"):  # Drop the rows of the earlier seeds.
        model.objects.using(alias).all().delete()
    return model


def minio_tile(model, alias, **changes):
    return model.objects.using(alias).create(**{**MINIO_RETIRED, **changes})


def replace(model):
    default_before = rows(model, "default")
    migrate("secondary", [REPLACEMENT])
    assert rows(model, "default") == default_before  # Only the migration connection changes.
    after = rows(model, "secondary")
    migrate("secondary", BEFORE_REPLACEMENT)
    assert rows(model, "secondary") == after  # The reverse keeps the replacement.
    assert rows(model, "default") == default_before
    return after


@pytest.mark.parametrize("logo", ["services/logos/minio.png", "services/logos/minio_Ab3dE9x.png"])
def test_retired_minio_tile_becomes_rustfs(at_initial, logo):
    model = before_replacement()
    for alias in ("default", "secondary"):
        tile_pk = minio_tile(model, alias, logo_file=logo, is_active=False, order=41).pk

    replace(model)

    tile = model.objects.using("secondary").get(pk=tile_pk)
    assert tile.name == "RustFS"
    assert tile.description == replacement_fields()["description"]
    assert tile.url == ""
    assert tile.icon == "fas fa-database"
    assert tile.logo_file.name == ""  # add_default_services fills the RustFS logo.
    assert (tile.is_active, tile.order) == (False, 41)  # Owner-managed fields stay.


def test_owner_description_icon_and_logo_survive_the_replacement(at_initial):
    model = before_replacement()
    tile_pk = minio_tile(
        model,
        "secondary",
        description="Owner text",
        icon="owner-icon",
        logo_file="services/logos/owner-storage.svg",
    ).pk

    replace(model)

    tile = model.objects.using("secondary").get(pk=tile_pk)
    assert (tile.name, tile.url) == ("RustFS", "")
    assert (tile.description, tile.icon, tile.logo_file.name) == (
        "Owner text",
        "owner-icon",
        "services/logos/owner-storage.svg",
    )


def test_minio_tile_with_an_owner_url_is_left_alone(at_initial):
    model = before_replacement()
    minio_tile(model, "secondary", url="https://owner.example/storage/")
    before = rows(model, "secondary")

    assert replace(model) == before


def test_existing_rustfs_tile_only_hides_the_retired_minio_tile(at_initial):
    model = before_replacement()
    minio_tile(model, "secondary")
    customize(model, "secondary", "RustFS")
    rustfs_before = model.objects.using("secondary").filter(name="RustFS").values().get()

    replace(model)

    assert model.objects.using("secondary").filter(name="RustFS").values().get() == rustfs_before
    minio = model.objects.using("secondary").get(name="MinIO")
    assert minio.is_active is False
    assert minio.url == MINIO_RETIRED["url"]


def test_replacement_without_a_minio_tile_changes_nothing(at_initial):
    model = before_replacement()
    customize(model, "secondary", "Unrelated secondary")
    before = rows(model, "secondary")

    assert replace(model) == before
