#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

"""
PublishWpCommand.py — Publishes HTML chapters to existing WordPress pages.

For each .html file in the folder (or the single file supplied):
  1. Extracts the chapter number from the filename via --slug-pattern.
  2. Builds the WP page URL by substituting {n} in --wp-url.
  3. Fetches the page via the REST API; errors out if the page does not exist.
  4. Compares modified_gmt (WP) with the local file mtime; skips if the file
     is not newer.
  5. Otherwise updates the page content with the HTML from the local file.

Authentication: HTTP Basic with a WordPress Application Password (--wp-user
and --wp-password, or the WP_USER / WP_PASSWORD environment variables).
Application Passwords are generated under Users → Profile → Application
Passwords and are not subject to 2FA.

HTML is cleaned before publishing via HtmlCleaner.clean_html(): the <head>,
comments, crosslinks, empty anchors, <span> tags, and all id attributes are
stripped, leaving a clean body fragment.
"""

import base64
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import certifi

from book_assistant.CommandBase import CommandBase
from book_assistant.Commons import cyan, debug, error, green, log, warning, yellow
from .HtmlCleaner import clean_html

_PUBLISH_WP_COMMAND = "publish-wp"

# WordPress REST API returns dates in ISO 8601 UTC, e.g. "2025-03-14T10:22:00"
_WP_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _parse_wp_date(date_str: str) -> datetime:
    """Parse a WP date string (ISO 8601 UTC, no trailing 'Z') into a UTC-aware datetime."""
    dt = datetime.strptime(date_str, _WP_DATE_FORMAT)
    return dt.replace(tzinfo=timezone.utc)


def _file_mtime(path: Path) -> datetime:
    """Return the file's mtime as a UTC-aware datetime."""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _api_base(wp_url: str) -> str:
    """Derive the WP REST API base URL from a page URL.

    Example: https://site.com/book/c1  →  https://site.com/wp-json/wp/v2/pages
    """
    parsed = urlparse(wp_url)
    return f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2/pages"


def _request(url: str, credentials: str, method: str = "GET", data: dict | None = None) -> dict:
    """Execute an HTTP call against the WordPress REST API.

    :param url:         full URL, query string included
    :param credentials: base64-encoded "user:app-password" string
    :param method:      "GET" or "POST"
    :param data:        dict to serialise as the JSON body (POST only)
    :return:            response deserialised as a dict or list
    :raises RuntimeError: on any HTTP or network error
    """
    body = json.dumps(data).encode("utf-8") if data else None
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    debug(f"{method} {url}")
    try:
        with urllib.request.urlopen(req, context=ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason} — {body_text[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e


def _find_page(api: str, credentials: str, slug: str) -> dict | None:
    """Look up a WP page by slug.

    :return: the first matching page as a dict, or None if not found.
    """
    url = f"{api}?slug={slug}&status=any&_fields=id,slug,link,modified_gmt"
    results = _request(url, credentials)
    if not isinstance(results, list) or len(results) == 0:
        return None
    return results[0]


def _update_page(api: str, credentials: str, page_id: int, html_content: str) -> dict:
    """Update the content of an existing WP page.

    :return: the API response (updated page object).
    """
    return _request(f"{api}/{page_id}", credentials, method="POST",
                    data={"content": html_content})


class PublishWpCommand(CommandBase):

    def __init__(self):
        super().__init__(_PUBLISH_WP_COMMAND)
        self._published = 0
        self._skipped   = 0
        self._errors    = 0

    def process_args(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--wp-url",
            default=None,
            help=(
                "WordPress page URL pattern with {n} as the chapter-number placeholder. "
                "Example: https://site.com/book/c{n}"
            ),
        )
        parser.add_argument(
            "--slug-pattern",
            default=r"ch(\d+)",
            help=(
                "Regex applied to the filename stem to extract the chapter number. "
                "The first capture group becomes {n}. "
                r"Default: 'ch(\d+)' — matches filenames such as 'BookCh3'."
            ),
        )
        parser.add_argument(
            "--wp-user",
            default=None,
            help="WordPress username. Alternatively, set the WP_USER environment variable.",
        )
        parser.add_argument(
            "--wp-password",
            default=None,
            help=(
                "WordPress Application Password (generated under Users → Profile → "
                "Application Passwords). Not subject to 2FA. "
                "Alternatively, set the WP_PASSWORD environment variable."
            ),
        )

    # ------------------------------------------------------------------
    # Override run(): iterate over *.html instead of *.txt, and validate
    # required options before any file is processed.
    # ------------------------------------------------------------------

    def run(self, args) -> None:
        user     = args.wp_user     or os.environ.get("WP_USER")
        password = args.wp_password or os.environ.get("WP_PASSWORD")
        if not user or not password:
            error("Missing credentials. Use --wp-user / --wp-password or set WP_USER / WP_PASSWORD.")
            return

        if not args.wp_url or "{n}" not in args.wp_url:
            error("--wp-url is required and must contain the {n} placeholder.")
            return

        try:
            slug_re = re.compile(args.slug_pattern)
        except re.error as e:
            error(f"--slug-pattern is not a valid regex: {e}")
            return

        path = Path(args.path).resolve()
        if not path.exists():
            error(f"Path does not exist: {args.path}")
            return

        self._credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
        self._wp_url      = args.wp_url
        self._slug_re     = slug_re
        self._dry_run     = args.dry_run

        try:
            self._prepare()
            if path.is_file():
                self._run(args, path)
            elif path.is_dir():
                html_files = sorted(path.rglob("*.html"))
                if not html_files:
                    warning(f"No .html files found in: {path}")
                for html_path in html_files:
                    self._run(args, html_path)
        finally:
            self._finish()

    # ------------------------------------------------------------------
    # Single-file processing
    # ------------------------------------------------------------------

    def _run(self, args, path: Path) -> None:
        # 1. Extract chapter number from the filename stem
        match = self._slug_re.search(path.stem)
        if not match:
            warning(f"{path.name}: slug-pattern '{self._slug_re.pattern}' did not match — skipped.")
            self._skipped += 1
            return

        chapter_n = match.group(1)

        # 2. Build the WP page URL and derive slug + API base
        page_url = self._wp_url.replace("{n}", chapter_n)
        slug     = urlparse(page_url).path.rstrip("/").split("/")[-1]
        api      = _api_base(page_url)

        log(f"{path.name}  →  {page_url}")

        # 3. Check that the page exists
        try:
            page = _find_page(api, self._credentials, slug)
        except RuntimeError as e:
            error(f"{path.name}: error looking up page — {e}")
            self._errors += 1
            return

        if page is None:
            error(f"{path.name}: page not found on WordPress (slug='{slug}').")
            self._errors += 1
            return

        debug(f"Page found: id={page['id']}  modified_gmt={page['modified_gmt']}")

        # 4. Compare dates
        try:
            wp_modified = _parse_wp_date(page["modified_gmt"])
        except (KeyError, ValueError) as e:
            error(f"{path.name}: cannot read WP modification date — {e}")
            self._errors += 1
            return

        file_mtime = _file_mtime(path)
        debug(f"File mtime: {file_mtime.isoformat()}   WP modified: {wp_modified.isoformat()}")

        if file_mtime <= wp_modified:
            log(yellow(f"  Skipped: file is not newer than the WP page "
                       f"({file_mtime.isoformat()} ≤ {wp_modified.isoformat()})."))
            self._skipped += 1
            return

        # 5. Publish
        if self._dry_run:
            log(cyan(f"  [dry-run] Would publish page id={page['id']} "
                     f"({file_mtime.isoformat()} > {wp_modified.isoformat()})."))
            self._published += 1
            return

        try:
            raw_html     = path.read_text(encoding="utf-8")
            html_content = clean_html(raw_html)
            _update_page(api, self._credentials, page["id"], html_content)
        except RuntimeError as e:
            error(f"{path.name}: error updating page — {e}")
            self._errors += 1
            return

        log(green(f"  Published (id={page['id']})."))
        self._published += 1

    def _finish(self) -> None:
        log(f"Published: {self._published}  |  Skipped: {self._skipped}  |  Errors: {self._errors}")
        super()._finish()
