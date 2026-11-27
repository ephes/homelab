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


ZELLIJ_REMOVAL = ("core", "0022_remove_retired_zellij_tile")
BEFORE_ZELLIJ_REMOVAL = [("core", "0021_service_logo_file_index")]
ZELLIJ_TILE = {
    "name": "Zellij (studio)",
    "description": "Web client for the zellij terminal multiplexer running on studio (tailnet only)",
    "url": "https://zellij.home.xn--wersdrfer-47a.de/",
    "icon": "fas fa-terminal",
    "is_active": True,
    "order": 27,
}


def before_zellij_removal():
    model = migrate("secondary", BEFORE_ZELLIJ_REMOVAL)
    for alias in ("default", "secondary"):  # Drop the rows of the earlier seeds.
        model.objects.using(alias).all().delete()
    return model


def remove_zellij(model):
    default_before = rows(model, "default")
    migrate("secondary", [ZELLIJ_REMOVAL])
    assert rows(model, "default") == default_before  # Only the migration connection changes.
    after = rows(model, "secondary")
    migrate("secondary", BEFORE_ZELLIJ_REMOVAL)
    assert rows(model, "secondary") == after  # The reverse keeps the removal.
    assert rows(model, "default") == default_before
    return after


@pytest.mark.parametrize("changes", [{}, {"name": "Terminal", "is_active": False, "order": 3}])
def test_retired_zellij_tile_is_deleted(at_initial, changes):
    model = before_zellij_removal()
    for alias in ("default", "secondary"):
        model.objects.using(alias).create(**{**ZELLIJ_TILE, **changes})
    customize(model, "secondary", "Unrelated secondary")
    unrelated = model.objects.using("secondary").filter(name="Unrelated secondary").values().get()

    after = remove_zellij(model)

    assert after == [unrelated]


def test_zellij_named_tile_with_another_url_is_left_alone(at_initial):
    model = before_zellij_removal()
    model.objects.using("secondary").create(**{**ZELLIJ_TILE, "url": "https://owner.example/terminal/"})
    before = rows(model, "secondary")

    assert remove_zellij(model) == before


TILE_REFRESH = ("core", "0023_refresh_service_tiles")
BEFORE_TILE_REFRESH = [ZELLIJ_REMOVAL]
OPEN_WEBUI_URL = "https://open-webui.home.xn--wersdrfer-47a.de/"
MAILGUN_URL = "https://mailgun.home.xn--wersdrfer-47a.de/"
FEDIVERSE_URL = "https://fedi.python-podcast.de/"
TAKAHE_DESCRIPTION = "Fediverse server for python-podcast.de"
GOTOSOCIAL_DESCRIPTION = "Fediverse server (GoToSocial) for python-podcast.de"


@pytest.fixture
def before_tile_refresh(at_initial):
    return migrate("secondary", BEFORE_TILE_REFRESH)


def apply_tile_refresh(model):
    default_before = rows(model, "default")
    migrate("secondary", [TILE_REFRESH])
    assert rows(model, "default") == default_before
    after = rows(model, "secondary")
    migrate("secondary", BEFORE_TILE_REFRESH)
    assert rows(model, "secondary") == after  # The reverse is a no-op.
    assert rows(model, "default") == default_before
    return after


def test_tile_refresh_keeps_fresh_fediverse_tile_active(before_tile_refresh):
    model = before_tile_refresh
    apply_tile_refresh(model)

    services = model.objects.using("secondary")
    tile = services.get(name="GoToSocial")
    assert tile.url == FEDIVERSE_URL
    assert tile.description == GOTOSOCIAL_DESCRIPTION
    assert tile.icon == "fas fa-comment-dots"
    assert tile.is_active is True
    assert tile.order == 18
    assert not services.filter(name__in=["Takahe", "Open WebUI"]).exists()


def test_tile_refresh_deletes_only_exact_retired_urls(before_tile_refresh):
    model = before_tile_refresh
    for alias in ("default", "secondary"):
        services = model.objects.using(alias)
        customize(model, alias, "Open WebUI")
        services.filter(name="Open WebUI").update(url=OPEN_WEBUI_URL.rstrip("/"))
        services.create(name="Custom chat", url=OPEN_WEBUI_URL, is_active=False, order=50)
        services.create(name="Custom relay", url=MAILGUN_URL)
        services.create(name="Mailgun Relay", url=f"{MAILGUN_URL}api/")
        customize(model, alias, "Takahe")  # Keep the focus on URL-based deletion.
        customize(model, alias, "Unrelated service")
    expected = [row for row in rows(model, "secondary") if row["name"] not in {"Custom chat", "Custom relay"}]

    assert apply_tile_refresh(model) == expected


@pytest.mark.parametrize("icon", ["fas fa-comment-dots", "fas fa-star", ""])
def test_tile_refresh_renames_takahe_in_place(before_tile_refresh, icon):
    model = before_tile_refresh
    for alias in ("default", "secondary"):
        tile = customize(model, alias, "Takahe")
        model.objects.using(alias).filter(pk=tile.pk).update(
            url=FEDIVERSE_URL, icon=icon, description=TAKAHE_DESCRIPTION
        )

    services = model.objects.using("secondary")
    before = services.values().get(name="Takahe")
    apply_tile_refresh(model)

    after = services.values().get(name="GoToSocial")
    assert after.pop("updated_at") != before.pop("updated_at")
    assert after == {
        **before,
        "name": "GoToSocial",
        "description": GOTOSOCIAL_DESCRIPTION,
    }


@pytest.mark.parametrize("description", ["Owner text", ""], ids=["custom", "blank"])
def test_tile_refresh_preserves_owner_description(before_tile_refresh, description):
    model = before_tile_refresh
    services = model.objects.using("secondary")
    services.filter(name="Takahe").update(description=description)
    tile_pk = services.get(name="Takahe").pk

    apply_tile_refresh(model)

    tile = services.get(pk=tile_pk)
    assert (tile.name, tile.description) == ("GoToSocial", description)


def test_tile_refresh_preserves_fediverse_url_without_trailing_slash(before_tile_refresh):
    model = before_tile_refresh
    services = model.objects.using("secondary")
    url = "https://fedi.python-podcast.de"
    services.filter(name="Takahe").update(url=url)
    tile_pk = services.get(name="Takahe").pk

    apply_tile_refresh(model)

    tile = services.get(pk=tile_pk)
    assert (tile.name, tile.url, tile.description) == ("GoToSocial", url, GOTOSOCIAL_DESCRIPTION)


def test_tile_refresh_requires_both_takahe_name_and_url(before_tile_refresh):
    model = before_tile_refresh
    services = model.objects.using("secondary")
    services.filter(name="Takahe").update(url="https://owner.example/fediverse/")
    services.create(name="Custom Fediverse", url=FEDIVERSE_URL)
    services.filter(name="Open WebUI").delete()
    before = rows(model, "secondary")

    assert apply_tile_refresh(model) == before


def test_tile_refresh_leaves_both_fediverse_tiles_when_gotosocial_exists(before_tile_refresh):
    model = before_tile_refresh
    model.objects.using("secondary").filter(name="Open WebUI").delete()
    customize(model, "secondary", "GoToSocial")
    before = rows(model, "secondary")

    assert apply_tile_refresh(model) == before


@pytest.mark.parametrize("url", [OPEN_WEBUI_URL, MAILGUN_URL], ids=["open-webui", "mailgun"])
def test_tile_refresh_clears_retired_gotosocial_collision_before_renaming(before_tile_refresh, url):
    model = before_tile_refresh
    services = model.objects.using("secondary")
    retired = services.create(name="GoToSocial", url=url)
    takahe = services.get(name="Takahe")

    apply_tile_refresh(model)

    assert not services.filter(pk=retired.pk).exists()
    assert services.get(name="GoToSocial").pk == takahe.pk


CLIENT_TILE_SWITCH = ("core", "0024_switch_client_tiles_to_production")


@pytest.fixture
def before_client_tile_switch(at_initial):
    return migrate("secondary", [TILE_REFRESH])


@pytest.fixture(
    params=[
        ("Projekt Heis", "https://heis.staging.django-cast.com/", "https://fabian-heis.de/"),
        ("Projekt Marina", "https://marina.staging.django-cast.com/", "https://marina-adler.de/"),
    ],
    ids=["heis", "marina"],
)
def client_site(request):
    return request.param


def apply_client_tile_switch(model):
    default_before = rows(model, "default")
    migrate("secondary", [CLIENT_TILE_SWITCH])
    assert rows(model, "default") == default_before
    after = rows(model, "secondary")
    migrate("secondary", [TILE_REFRESH])
    assert rows(model, "secondary") == after  # The reverse is a no-op.
    assert rows(model, "default") == default_before
    return after


@pytest.mark.parametrize("trailing_slash", [True, False], ids=["with-slash", "without-slash"])
def test_client_tile_switch_updates_matching_tile_in_place(before_client_tile_switch, client_site, trailing_slash):
    model = before_client_tile_switch
    name, staging_url, production_url = client_site
    old_name = f"{name} (Staging)"
    project = name.removeprefix("Projekt ")
    for alias in ("default", "secondary"):
        tile = customize(model, alias, old_name)
        model.objects.using(alias).filter(pk=tile.pk).update(
            url=staging_url if trailing_slash else staging_url.rstrip("/"),
            description=f"Client project staging site for {project}",
        )

    services = model.objects.using("secondary")
    for other_project, slug in [
        ("GGS Lennestraße", "ggs"),
        ("Villa Kunterbunt", "villakunterbunt"),
        ("Django Chat", "djangochat"),
    ]:
        services.create(
            name=f"Projekt {other_project} (Staging)",
            url=f"https://{slug}.staging.django-cast.com/",
        )
    other_tiles = list(services.exclude(name=old_name).order_by("pk").values())
    before = services.values().get(name=old_name)

    apply_client_tile_switch(model)

    after = services.values().get(name=name)
    assert after.pop("updated_at") != before.pop("updated_at")
    assert after == {
        **before,
        "name": name,
        "url": production_url,
        "description": f"Client project production site for {project}",
    }
    assert list(services.exclude(name=name).order_by("pk").values()) == other_tiles


@pytest.mark.parametrize("description", ["Owner text", ""], ids=["custom", "blank"])
def test_client_tile_switch_preserves_owner_description(before_client_tile_switch, client_site, description):
    model = before_client_tile_switch
    name, staging_url, production_url = client_site
    services = model.objects.using("secondary")
    tile = services.create(name=f"{name} (Staging)", url=staging_url, description=description)

    apply_client_tile_switch(model)

    tile = services.get(pk=tile.pk)
    assert (tile.name, tile.url, tile.description) == (name, production_url, description)


def test_client_tile_switch_requires_both_staging_name_and_url(before_client_tile_switch, client_site):
    model = before_client_tile_switch
    name, staging_url, _ = client_site
    customize(model, "secondary", f"{name} (Staging)")
    model.objects.using("secondary").create(name="Custom staging tile", url=staging_url)
    before = rows(model, "secondary")

    assert apply_client_tile_switch(model) == before


def test_client_tile_switch_leaves_both_tiles_when_production_name_exists(before_client_tile_switch, client_site):
    model = before_client_tile_switch
    name, staging_url, _ = client_site
    model.objects.using("secondary").create(name=f"{name} (Staging)", url=staging_url)
    customize(model, "secondary", name)
    before = rows(model, "secondary")

    assert apply_client_tile_switch(model) == before
