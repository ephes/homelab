import os
import stat
from contextlib import suppress
from pathlib import Path

from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import router, transaction

from apps.core.logo_storage import write_logo_chunk
from apps.core.models import Service


class NonregularPackagedLogoError(OSError):
    pass


def open_regular_logo(path, flags):
    # A FIFO can block during open, before its descriptor can be checked.
    fd = os.open(path, flags | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise NonregularPackagedLogoError(path)
    except BaseException:
        os.close(fd)
        raise
    return fd


class Command(BaseCommand):
    help = "Create missing default services and fill missing logos"

    def _default_services(self):
        return [
            {
                "name": "Home Assistant",
                "description": "Smart home automation platform for controlling lights, sensors, and devices",
                "url": "https://homeassistant.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-home",
                "logo_filename": "home-assistant.png",
                "order": 1,
            },
            {
                "name": "Nyxmon",
                "description": "System monitoring and metrics dashboard for homelab infrastructure",
                "url": "https://nyxmon.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-chart-line",
                "logo_filename": "nyxmon.png",
                "order": 2,
            },
            {
                "name": "Unifi",
                "description": "Self-hosted network controller for managing WiFi access points and switches",
                "url": "https://unifi.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-network-wired",
                "logo_filename": "unifi.png",
                "order": 3,
            },
            {
                "name": "Paperless-ngx",
                "description": "Document management system for transforming paper into searchable digital archives",
                "url": "https://paperless.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-file-alt",
                "logo_filename": "paperless.png",
                "order": 4,
            },
            {
                "name": "FastDeploy",
                "description": "Deployment automation platform for managing web applications via API and web interface",
                "url": "https://deploy.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-rocket",
                "order": 5,
            },
            {
                "name": "Vaultwarden",
                "description": "Self-hosted password manager compatible with Bitwarden clients",
                "url": "https://vault.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-lock",
                "logo_filename": "vaultwarden.svg",
                "order": 6,
            },
            {
                "name": "SnappyMail",
                "description": "Self-hosted webmail client for IMAP/SMTP access",
                "url": "https://webmail.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-envelope",
                "logo_filename": "snappymail.svg",
                "order": 7,
            },
            {
                # MinIO was retired on 2026-11-17; migration 0018 turns its tile
                # into this one. RustFS has no web console, so there is no link.
                "name": "RustFS",
                "description": (
                    "S3-compatible object storage (RustFS on Fractal) for backups and application data. "
                    "S3 API at https://s3.home.xn--wersdrfer-47a.de/ "
                    "(LAN and Tailnet, signed requests only, no web console)"
                ),
                "url": "",
                "icon": "fas fa-database",
                "logo_filename": "rustfs.png",
                "order": 8,
            },
            {
                "name": "Navidrome",
                "description": "Self-hosted music streaming server (Subsonic-compatible)",
                "url": "https://music.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-music",
                "logo_filename": "navidrome.png",
                "order": 9,
            },
            {
                "name": "Jellyfin",
                "description": "Self-hosted video server for movies, TV, and downloads",
                "url": "https://media.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-film",
                "logo_filename": "jellyfin.svg",
                "order": 10,
            },
            {
                "name": "MeTube",
                "description": "Share-sheet video downloader to Jellyfin (yt-dlp queue)",
                "url": "https://metube.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-cloud-download-alt",
                "order": 11,
            },
            {
                "name": "Minecraft",
                "description": "Java Edition server - Connect at macmini.fritz.box:25565",
                "url": "",
                "icon": "fas fa-cube",
                "logo_filename": "minecraft.png",
                "order": 12,
            },
            {
                "name": "PostfixAdmin",
                "description": "Mail user and alias management for self-hosted email",
                "url": "https://mailadmin.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-users-cog",
                "logo_filename": "postfixadmin.svg",
                "order": 13,
            },
            {
                "name": "Fractal IPMI",
                "description": "IPMI/BMC management interface for the fractal server",
                "url": "https://asrock.fritz.box/",
                "icon": "fas fa-microchip",
                "logo_filename": "fractal-ipmi.svg",
                "is_active": True,
                "order": 14,
            },
            {
                "name": "Family Blog CMS",
                "description": "Wagtail admin for the family blog",
                "url": "https://wersdoerfer.de/cms",
                "icon": "fas fa-feather-alt",
                "logo_filename": "wagtail.svg",
                "order": 15,
            },
            {
                "name": "Python Podcast CMS",
                "description": "Wagtail admin for python-podcast.de",
                "url": "https://python-podcast.de/cms",
                "icon": "fas fa-podcast",
                "logo_filename": "wagtail.svg",
                "order": 16,
            },
            {
                "name": "qBittorrent",
                "description": "BitTorrent client for downloads and seeding",
                "url": "https://torrent.home.wersdörfer.de",
                "icon": "fas fa-magnet",
                "logo_filename": "qbittorrent.svg",
                "order": 17,
            },
            {
                "name": "GoToSocial",
                "description": "Fediverse server (GoToSocial) for python-podcast.de",
                "url": "https://fedi.python-podcast.de/",
                "icon": "fas fa-comment-dots",
                "order": 18,
            },
            {
                "name": "Mastodon",
                "description": "Mastodon instance for wersdoerfer.de",
                "url": "https://fedi.wersdoerfer.de/",
                "icon": "fab fa-mastodon",
                "order": 19,
            },
            # Open WebUI, order 20, was retired. Migration 0023 removes its tile.
            {
                "name": "Echoport",
                "description": "Backup orchestration service for SQLite databases and config files",
                "url": "https://echoport.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-cloud-upload-alt",
                "logo_filename": "echoport.svg",
                "order": 21,
            },
            {
                "name": "OpenClaw",
                "description": "AI automation gateway and web dashboard",
                "url": "https://openclaw.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-robot",
                "logo_filename": "openclaw.svg",
                "order": 22,
            },
            {
                "name": "Voxhelm",
                "description": "Operator UI for local audio/video transcription and transcript exports",
                "url": "https://voxhelm.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-wave-square",
                "order": 23,
            },
            {
                "name": "Graphyard",
                "description": "Metrics catalog and operator interface for the homelab metrics platform",
                "url": "https://graphyard.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-project-diagram",
                "logo_filename": "graphyard.svg",
                "order": 24,
            },
            {
                "name": "Grafana",
                "description": "Time-series dashboards and drill-down views for Graphyard metrics",
                "url": "https://grafana.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-chart-area",
                "order": 25,
            },
            {
                "name": "OpsGate",
                "description": "Approval queue and audit surface for human-reviewed operator actions",
                "url": "https://opsgate.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-clipboard-check",
                "order": 25,
            },
            {
                "name": "Archive",
                "description": (
                    "Self-hosted archive for saved links, podcast episodes, and videos with summaries and public feeds"
                ),
                "url": "https://archive.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-box-archive",
                "order": 26,
            },
            # Zellij (studio), order 27, was retired on 2026-11-27; migration 0022
            # deletes its installed tile.
            # Mailgun Relay, order 28, is API-only. Migration 0023 removes its tile.
            {
                "name": "Recorder",
                "description": (
                    "Remote podcast recording — browser local-master double-ender capture "
                    "with resumable upload and per-track WAV export"
                ),
                "url": "https://recorder.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-microphone",
                "order": 29,
            },
            {
                "name": "Work",
                "description": "Agent work ledger — what needs me, in progress, blocked, recently finished",
                "url": "https://work.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-tasks",
                "order": 30,
            },
            {
                "name": "Haushalt",
                "description": "Family finance dashboard",
                "url": "https://haushalt.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-wallet",
                "order": 31,
            },
            {
                "name": "Opaq",
                "description": "Company cash overview",
                "url": "https://opaq.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-chart-line",
                "order": 32,
            },
            {
                "name": "Fallakte",
                "description": "Private legal case files",
                "url": "https://akte.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-folder-open",
                "order": 33,
            },
            {
                "name": "Chesslab",
                "description": "Chess spaced-repetition trainer",
                "url": "https://chess.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-chess-knight",
                "order": 34,
            },
            {
                "name": "Weeknotes",
                "description": "Weeknotes steering inbox and draft review",
                "url": "https://weeknotes.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-inbox",
                "order": 35,
            },
            {
                "name": "Radarr",
                "description": "Movie download automation",
                "url": "https://radarr.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-film",
                "order": 36,
            },
            {
                "name": "Sonarr",
                "description": "TV series download automation",
                "url": "https://sonarr.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-tv",
                "order": 37,
            },
            {
                "name": "Prowlarr",
                "description": "Indexer management for Radarr and Sonarr",
                "url": "https://prowlarr.home.xn--wersdrfer-47a.de/",
                "icon": "fas fa-list",
                "order": 38,
            },
            {
                "name": "Durchreiche",
                "description": "Invite-only inquiry exchange",
                "url": "https://durchreiche.wersdoerfer.de/",
                "icon": "fas fa-exchange-alt",
                "order": 39,
            },
            # Client project sites.
            {
                "name": "Projekt GGS Lennestraße (Staging)",
                "description": "Client project staging site for GGS Lennestraße",
                "url": "https://ggs.staging.django-cast.com/",
                "icon": "fas fa-flask",
                "order": 40,
            },
            {
                "name": "Projekt Villa Kunterbunt (Staging)",
                "description": "Client project staging site for Villa Kunterbunt",
                "url": "https://villakunterbunt.staging.django-cast.com/",
                "icon": "fas fa-flask",
                "order": 41,
            },
            {
                "name": "Projekt Django Chat (Staging)",
                "description": "Client project staging site for Django Chat",
                "url": "https://djangochat.staging.django-cast.com/",
                "icon": "fas fa-flask",
                "order": 42,
            },
            {
                "name": "Projekt Heis",
                "description": "Client project production site for Heis",
                "url": "https://fabian-heis.de/",
                "icon": "fas fa-flask",
                "order": 43,
            },
            {
                "name": "Projekt Marina",
                "description": "Client project production site for Marina",
                "url": "https://marina-adler.de/",
                "icon": "fas fa-flask",
                "order": 44,
            },
        ]

    def handle(self, *args, **options):
        using = router.db_for_write(Service)
        if not transaction.get_autocommit(using=using):
            raise CommandError(f"add_default_services requires autocommit on database '{using}'.")

        logos_dir = Path(__file__).parent.parent.parent / "static" / "core" / "logos"

        # Logo files are written to storage right away, but the service rows only
        # become permanent when the transaction commits. Remember every file this
        # run stores so a failed run can take them back out again.
        stored_logo_names: list[str] = []
        messages: list[str] = []
        warnings: list[str] = []
        logo_storage = Service._meta.get_field("logo_file").storage
        committed = False

        def report_success():
            nonlocal committed
            committed = True
            for message in messages:
                self.stdout.write(self.style.SUCCESS(message))
            for warning in warnings:
                self.stderr.write(self.style.WARNING(warning))
            self.stdout.write(self.style.SUCCESS(f"\nTotal services in database: {total}"))
            # A buffered pipe can fail only when flushed.
            self.stdout.flush()
            if warnings:
                self.stderr.flush()

        try:
            with transaction.atomic(using=using):
                for service_data in self._default_services():
                    logo_filename = service_data.pop("logo_filename", None)

                    service, created = Service.objects.using(using).get_or_create(
                        name=service_data["name"], defaults=service_data
                    )

                    if logo_filename and not service.logo_file:
                        logo_path = logos_dir / logo_filename
                        try:
                            source = open(logo_path, "rb", opener=open_regular_logo)
                        except FileNotFoundError:
                            warnings.append(
                                f"Missing packaged logo {logo_filename} for {service.name} (using icon fallback)"
                            )
                        except NonregularPackagedLogoError:
                            warnings.append(
                                f"Nonregular packaged logo {logo_filename} for {service.name} (using icon fallback)"
                            )
                        else:
                            with source:
                                opened = os.fstat(source.fileno())
                                # Reserve and record an exclusively owned name
                                # before copying any bytes so cleanup can remove
                                # even a partially written logo.
                                logo_field = service.logo_file.field
                                reserved_name = logo_storage.save(
                                    logo_field.generate_filename(service, logo_filename),
                                    ContentFile(b""),
                                    max_length=logo_field.max_length,
                                )
                                stored_logo_names.append(reserved_name)
                                remaining = opened.st_size
                                with logo_storage.open(reserved_name, "wb") as destination:
                                    while remaining:
                                        chunk = source.read(min(remaining, File.DEFAULT_CHUNK_SIZE))
                                        if not chunk:
                                            break
                                        write_logo_chunk(destination, chunk)
                                        remaining -= len(chunk)
                                copied = os.fstat(source.fileno())
                                if remaining or (
                                    copied.st_size,
                                    copied.st_mtime_ns,
                                    copied.st_ctime_ns,
                                ) != (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns):
                                    raise OSError(f"Packaged logo changed while copying: {logo_filename}")
                            # Storage I/O may outlive an owner edit. Reload and lock
                            # before attaching, and write only the logo and revision.
                            service = Service.objects.using(using).select_for_update().get(pk=service.pk)
                            if service.logo_file:
                                # Relinquish ownership before deletion: another
                                # upload can reuse the freed name immediately.
                                stored_logo_names.remove(reserved_name)
                                self._remove_stored_logos(logo_storage, [reserved_name], using)
                            else:
                                service.logo_file.name = reserved_name
                                service.save(using=using, update_fields=["logo_file", "updated_at"])
                                messages.append(f"Added logo for {service.name}")

                    status = "Created" if created else "Kept"
                    messages.append(f"{status} service: {service.name}")

                total = Service.objects.using(using).count()
                transaction.on_commit(report_success, using=using)
        except BaseException as error:
            if not committed:
                # An earlier on_commit callback can fail before the reporter.
                # Only compensate allocations verified unreferenced on the write DB.
                self._remove_stored_logos(logo_storage, stored_logo_names, using)
            elif isinstance(error, Exception):
                raise CommandError(
                    f"Service seed committed on database '{using}' (total services: {total}). Output failed ({error})."
                ) from error
            raise

    def _remove_stored_logos(self, storage, names: list[str], using: str) -> None:
        if not names:
            return
        try:
            # The seed list bounds the number of allocations in this lookup.
            referenced = set(
                Service.objects.using(using)
                .filter(logo_file__in=names)
                .order_by()
                .values_list("logo_file", flat=True)
                .distinct()
            )
        except Exception as error:  # noqa: BLE001 - retain allocations if ownership is unknown
            with suppress(Exception):
                self.stderr.write(self.style.WARNING(f"Could not check references for seed logo files: {error}"))
            return

        for name in names:
            if name in referenced:
                continue
            # A failed diagnostic must not interrupt cleanup or replace a seed error.
            with suppress(Exception):
                try:
                    storage.delete(name)
                except Exception as error:  # noqa: BLE001 - report the failure and keep cleaning up
                    self.stderr.write(self.style.WARNING(f"Could not remove logo file {name}: {error}"))
                else:
                    self.stderr.write(f"Removed logo file {name} (unused allocation)")
