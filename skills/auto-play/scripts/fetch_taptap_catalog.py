#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from build_tower_character_index import (
    CATALOG_SUPPLEMENTS_FILENAME,
    build_character_index,
    load_catalog,
    merge_catalog_entries,
    render_markdown,
)

APP_ID = '225735'
BASE_URL = 'https://www.taptap.cn'
SEED_URL = f'{BASE_URL}/app/{APP_ID}/strategy?os=android'
DEFAULT_XUA = (
    'V%3D1%26PN%3DWebApp%26LANG%3Dzh_CN%26VN_CODE%3D102%26LOC%3DCN%26'
    'PLT%3DPC%26DS%3DAndroid%26UID%3D271a85c0-79b2-4131-81a1-2183b3c634b9'
    '%26DT%3DPC'
)
TARGET_CATALOGS = {'卡牌图鉴', '宝物图鉴', '天赋图鉴'}
DEFAULT_TOWER_GUIDE_ROOT = Path('/Users/chunzhang/games/skills/game-tower/guide')
FIELD_ALIASES = {
    '类型': 'type',
    '消耗': 'cost',
    '效果': 'effect',
    '来源': 'source',
    '卡牌更新': 'updated',
    '宝物更新': 'updated',
    '更新时间': 'updated',
    '天赋': 'talent',
}


@dataclass(frozen=True)
class CatalogSeedEntry:
    catalog: str
    group: str
    name: str
    moment_id: str
    web_url: str
    icon_url: str
    order: int


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def game_root(game: str) -> Path:
    return repo_root() / 'skills' / 'auto-play' / 'games' / slugify_ascii(game)


def guide_root(game: str) -> Path:
    if slugify_ascii(game) == 'tower':
        path = Path(os.environ.get('TOWER_GUIDE_ROOT', str(DEFAULT_TOWER_GUIDE_ROOT)))
    else:
        path = game_root(game) / 'guide'
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify_ascii(value: str) -> str:
    slug = re.sub(r'[^0-9A-Za-z._-]+', '-', value.strip().lower()).strip('-')
    return slug or 'item'


def slugify_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', '-', value.strip()).strip('-')
    cleaned = re.sub(r'-+', '-', cleaned)
    return cleaned or fallback


def request_json(url: str, *, referer: str, retries: int = 3) -> dict[str, Any]:
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Referer': referer,
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'
        ),
    }
    last_error: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f'Failed to fetch JSON from {url}: {last_error}')


def download_file(url: str, path: Path, *, referer: str, force: bool = False) -> bool:
    if not url:
        return False
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        'Accept': 'image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5',
        'Referer': referer,
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'
        ),
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as response:
        path.write_bytes(response.read())
    return True


def landing_url(xua: str) -> str:
    return f'{BASE_URL}/webapiv2/game-guide/v1/landing?X-UA={xua}&app_id={APP_ID}'


def detail_url(moment_id: str, xua: str) -> str:
    return f'{BASE_URL}/webapiv2/moment/v3/detail?X-UA={xua}&id={moment_id}'


def image_url(image: dict[str, Any] | None) -> str:
    if not isinstance(image, dict):
        return ''
    for key in ('original_url', 'large_url', 'url', 'medium_url', 'small_url'):
        value = str(image.get(key) or '').strip()
        if value:
            return value
    return ''


def image_extension(url: str, fallback: str = '.png') -> str:
    path = urllib.parse.urlparse(url).path
    for suffix in ('.png', '.jpg', '.jpeg', '.webp', '.gif'):
        if suffix in path.lower():
            return '.jpg' if suffix == '.jpeg' else suffix
    return fallback


def extract_moment_id(entry: dict[str, Any]) -> str:
    uri = str(entry.get('uri') or '')
    match = re.search(r'moment_id=(\d+)', uri)
    if match:
        return match.group(1)
    web_url = str(entry.get('web_url') or '')
    match = re.search(r'/moment/(\d+)', web_url)
    return match.group(1) if match else ''


def extract_seed_entries(
    landing: dict[str, Any],
    *,
    catalogs: set[str],
    limit: int = 0,
) -> list[CatalogSeedEntry]:
    entries: list[CatalogSeedEntry] = []
    for block in landing.get('data', {}).get('list', []):
        index = block.get('index') or {}
        catalog = str(index.get('name') or '').strip()
        if catalog not in catalogs:
            continue
        for group in index.get('list') or []:
            group_name = str(group.get('name') or '').strip()
            for entry in group.get('list') or []:
                moment_id = extract_moment_id(entry)
                if not moment_id:
                    continue
                entries.append(
                    CatalogSeedEntry(
                        catalog=catalog,
                        group=group_name,
                        name=str(entry.get('name') or '').strip(),
                        moment_id=moment_id,
                        web_url=f'{BASE_URL}{entry.get("web_url") or ""}',
                        icon_url=image_url(entry.get('image')),
                        order=len(entries) + 1,
                    )
                )
                if limit and len(entries) >= limit:
                    return entries
    return entries


def parse_summary_fields(summary: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r'^([^:：]{1,12})[:：](.*)$', line)
        if not match:
            fields.setdefault('notes', line)
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        canonical = FIELD_ALIASES.get(key, key)
        if canonical in fields and value:
            fields[canonical] = f'{fields[canonical]}; {value}'
        else:
            fields[canonical] = value
    return fields


def bracket_terms(text: str) -> list[str]:
    terms = re.findall(r'[［\[]([^［\]\[\]]+)[\]］]', text)
    deduped: list[str] = []
    seen = set()
    for term in terms:
        term = term.strip()
        if term and term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def normalize_entry(
    seed: CatalogSeedEntry,
    detail: dict[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Any]:
    moment = detail.get('data', {}).get('moment') or {}
    topic = moment.get('topic') or {}
    title = str(topic.get('title') or seed.name).strip() or seed.name
    summary = str(topic.get('summary') or '').strip()
    fields = parse_summary_fields(summary)
    effect = fields.get('effect', '')
    local_name = f'{seed.order:03d}-{slugify_name(title, seed.moment_id)}'
    icon_ext = image_extension(seed.icon_url)
    icon_path = output_dir / 'images' / 'icons' / f'{local_name}{icon_ext}'

    detail_image_urls = [
        image_url(image) for image in topic.get('images') or [] if image_url(image)
    ]
    detail_image_paths = [
        output_dir
        / 'images'
        / 'details'
        / f'{local_name}-{index}{image_extension(url)}'
        for index, url in enumerate(detail_image_urls, start=1)
    ]
    search_text = '\n'.join(
        value
        for value in [
            title,
            seed.name,
            seed.catalog,
            seed.group,
            summary,
            fields.get('type', ''),
            fields.get('cost', ''),
            effect,
            fields.get('source', ''),
            fields.get('updated', ''),
        ]
        if value
    )
    related_terms = bracket_terms(summary)
    return {
        'name': title,
        'catalog': seed.catalog,
        'group': seed.group,
        'moment_id': seed.moment_id,
        'url': seed.web_url,
        'summary': summary,
        'fields': fields,
        'type': fields.get('type', ''),
        'cost': fields.get('cost', ''),
        'effect': effect,
        'source': fields.get('source', ''),
        'updated': fields.get('updated', ''),
        'related_terms': related_terms,
        'search_text': search_text,
        'icon_url': seed.icon_url,
        'icon_path': str(icon_path.relative_to(output_dir)) if seed.icon_url else '',
        'detail_image_urls': detail_image_urls,
        'detail_image_paths': [
            str(path.relative_to(output_dir)) for path in detail_image_paths
        ],
        'created_time': moment.get('created_time'),
        'edited_time': moment.get('edited_time'),
        'publish_time': moment.get('publish_time'),
    }


def fetch_detail(seed: CatalogSeedEntry, *, xua: str) -> tuple[CatalogSeedEntry, dict]:
    return seed, request_json(detail_url(seed.moment_id, xua), referer=seed.web_url)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def markdown_escape(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', '<br>')


def render_catalog_markdown(entries: list[dict[str, Any]], *, seed_url: str) -> str:
    lines = [
        '# TapTap Catalog Index',
        '',
        f'Source: {seed_url}',
        '',
        'This index contains TapTap catalog entries fetched from 卡牌图鉴, '
        '宝物图鉴, and 天赋图鉴. Use substring search over name, group, type, '
        'effect, source, and bracketed related terms.',
        '',
        '## Query Examples',
        '',
        '- `python scripts/search_taptap_catalog.py 超越卡牌`',
        '- `python scripts/search_taptap_catalog.py --catalog 卡牌图鉴 超越`',
        '- `python scripts/search_taptap_catalog.py --field effect 使用超越牌时`',
        '- `python scripts/search_taptap_catalog.py '
        '--group 超越卡牌 --field effect 增加`',
        '- `python scripts/search_taptap_catalog.py "使用卡牌时"`',
        '- `rg -n "超越卡牌|超越牌" /Users/chunzhang/games/skills/game-tower/guide`',
        '',
        '## Counts',
        '',
    ]
    counts: dict[str, dict[str, int]] = {}
    for entry in entries:
        counts.setdefault(entry['catalog'], {})
        counts[entry['catalog']][entry['group']] = (
            counts[entry['catalog']].get(entry['group'], 0) + 1
        )
    for catalog, groups in counts.items():
        lines.append(f'### {catalog}')
        lines.append('')
        for group, count in groups.items():
            lines.append(f'- {group}: {count}')
        lines.append('')
    lines.extend(
        [
            '## Entries',
            '',
            '| Catalog | Group | Name | Type | Cost | Effect | Source | Images |',
            '| --- | --- | --- | --- | --- | --- | --- | --- |',
        ]
    )
    for entry in entries:
        images: list[str] = []
        if entry.get('icon_path'):
            images.append(f'[icon]({entry["icon_path"]})')
        if entry.get('detail_image_paths'):
            images.append(f'[detail]({entry["detail_image_paths"][0]})')
        lines.append(
            '| '
            + ' | '.join(
                [
                    markdown_escape(entry.get('catalog', '')),
                    markdown_escape(entry.get('group', '')),
                    (
                        f'[{markdown_escape(entry.get("name", ""))}]'
                        f'({entry.get("url", "")})'
                    ),
                    markdown_escape(entry.get('type', '')),
                    markdown_escape(entry.get('cost', '')),
                    markdown_escape(entry.get('effect', '')),
                    markdown_escape(entry.get('source', '')),
                    ', '.join(images),
                ]
            )
            + ' |'
        )
    return '\n'.join(lines) + '\n'


def render_cards_markdown(entries: list[dict[str, Any]], *, seed_url: str) -> str:
    card_entries = [entry for entry in entries if entry['catalog'] == '卡牌图鉴']
    lines = [
        '# TapTap Card Index',
        '',
        f'Source: {seed_url}',
        '',
        '## Quick Queries',
        '',
        '- `python scripts/search_taptap_catalog.py --catalog 卡牌图鉴 超越卡牌`',
        '- `python scripts/search_taptap_catalog.py '
        '--catalog 卡牌图鉴 --field effect 使用超越牌时`',
        '- `python scripts/search_taptap_catalog.py --catalog 卡牌图鉴 "物理伤害"`',
        '- `python scripts/search_taptap_catalog.py --catalog 卡牌图鉴 "使用卡牌时"`',
        '',
    ]
    current_group = ''
    for entry in card_entries:
        if entry['group'] != current_group:
            current_group = entry['group']
            lines.extend([f'## {current_group}', ''])
        icon = (
            f'![{entry["name"]}]({entry["icon_path"]}) '
            if entry.get('icon_path')
            else ''
        )
        lines.append(
            f'- {icon}[{entry["name"]}]({entry["url"]})'
            f' - 类型: {entry.get("type") or "unknown"}'
            f'; 消耗: {entry.get("cost") or "unknown"}'
            f'; 效果: {entry.get("effect") or "unknown"}'
        )
    return '\n'.join(lines) + '\n'


def build_search_index(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'name': entry['name'],
            'catalog': entry['catalog'],
            'group': entry['group'],
            'type': entry.get('type', ''),
            'cost': entry.get('cost', ''),
            'effect': entry.get('effect', ''),
            'source': entry.get('source', ''),
            'related_terms': entry.get('related_terms', []),
            'url': entry.get('url', ''),
            'icon_path': entry.get('icon_path', ''),
            'detail_image_paths': entry.get('detail_image_paths', []),
            'search_text': entry.get('search_text', ''),
        }
        for entry in entries
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Fetch TapTap catalog entries for the tower game guide.'
    )
    parser.add_argument('--game', default='tower')
    parser.add_argument('--xua', default=DEFAULT_XUA)
    parser.add_argument(
        '--catalog',
        action='append',
        choices=sorted(TARGET_CATALOGS),
        help='Catalog section to fetch. Repeat to fetch multiple sections.',
    )
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--max-workers', type=int, default=8)
    parser.add_argument('--skip-images', action='store_true')
    parser.add_argument('--force-images', action='store_true')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = guide_root(args.game)
    catalogs = set(args.catalog or TARGET_CATALOGS)
    landing = request_json(landing_url(args.xua), referer=SEED_URL)
    seeds = extract_seed_entries(landing, catalogs=catalogs, limit=args.limit)
    print(f'Fetched landing index with {len(seeds)} entries.')

    details: list[tuple[CatalogSeedEntry, dict[str, Any]]] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as executor:
        futures = {
            executor.submit(fetch_detail, seed, xua=args.xua): seed for seed in seeds
        }
        for index, future in enumerate(as_completed(futures), start=1):
            seed = futures[future]
            try:
                details.append(future.result())
            except Exception as error:  # noqa: BLE001 - preserve fetch failure detail.
                failures.append(
                    {
                        'name': seed.name,
                        'moment_id': seed.moment_id,
                        'url': seed.web_url,
                        'error': str(error),
                    }
                )
            if index % 50 == 0 or index == len(seeds):
                print(f'Fetched {index}/{len(seeds)} detail records.')

    detail_by_id = {seed.moment_id: detail for seed, detail in details}
    entries = [
        normalize_entry(seed, detail_by_id[seed.moment_id], output_dir=output_dir)
        for seed in seeds
        if seed.moment_id in detail_by_id
    ]

    if not args.skip_images:
        image_jobs: list[tuple[str, Path, str]] = []
        for entry in entries:
            if entry.get('icon_url') and entry.get('icon_path'):
                image_jobs.append(
                    (
                        entry['icon_url'],
                        output_dir / entry['icon_path'],
                        entry['url'],
                    )
                )
            for url, rel_path in zip(
                entry.get('detail_image_urls', []),
                entry.get('detail_image_paths', []),
            ):
                image_jobs.append((url, output_dir / rel_path, entry['url']))
        downloaded = 0
        image_failures: list[dict[str, str]] = []
        with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as executor:
            futures = {
                executor.submit(
                    download_file,
                    url,
                    path,
                    referer=referer,
                    force=args.force_images,
                ): (url, path)
                for url, path, referer in image_jobs
            }
            for index, future in enumerate(as_completed(futures), start=1):
                url, path = futures[future]
                try:
                    if future.result():
                        downloaded += 1
                except Exception as error:  # noqa: BLE001 - preserve image errors.
                    image_failures.append(
                        {'url': url, 'path': str(path), 'error': str(error)}
                    )
                if index % 100 == 0 or index == len(image_jobs):
                    print(f'Processed {index}/{len(image_jobs)} images.')
        failures.extend(
            {
                'name': 'image download',
                'moment_id': '',
                'url': failure['url'],
                'error': failure['error'],
            }
            for failure in image_failures
        )
        print(f'Downloaded {downloaded} new images.')

    payload = {
        'source_url': SEED_URL,
        'app_id': APP_ID,
        'fetched_catalogs': sorted(catalogs),
        'entry_count': len(entries),
        'failure_count': len(failures),
        'failures': failures,
        'entries': entries,
    }
    supplement_path = output_dir / CATALOG_SUPPLEMENTS_FILENAME
    supplements = load_catalog(supplement_path) if supplement_path.exists() else []
    indexed_entries = merge_catalog_entries(entries, supplements)
    payload['supplement_file'] = str(supplement_path) if supplements else ''
    payload['supplement_count'] = len(indexed_entries) - len(entries)
    write_json(output_dir / 'taptap_catalog.json', payload)
    write_json(
        output_dir / 'taptap_search_index.json', build_search_index(indexed_entries)
    )
    (output_dir / 'taptap_catalog.md').write_text(
        render_catalog_markdown(entries, seed_url=SEED_URL)
    )
    (output_dir / 'taptap_cards.md').write_text(
        render_cards_markdown(entries, seed_url=SEED_URL)
    )
    characters = build_character_index(indexed_entries)
    write_json(
        output_dir / 'taptap_characters.json',
        {
            'source_catalog': str(output_dir / 'taptap_catalog.json'),
            'source_supplements': str(supplement_path) if supplements else '',
            'character_count': len(characters),
            'characters': characters,
        },
    )
    write_json(
        output_dir / 'taptap_character_index.json',
        {'entries': characters},
    )
    (output_dir / 'taptap_characters.md').write_text(render_markdown(characters))
    print(f'Wrote catalog guide to {output_dir}')
    if failures:
        print(f'Completed with {len(failures)} failures; see taptap_catalog.json.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
