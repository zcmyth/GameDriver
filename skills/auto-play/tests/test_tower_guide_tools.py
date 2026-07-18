import importlib.util
import sys
from pathlib import Path


def load_script(name):
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(name, scripts / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_character_names_from_multi_character_source():
    module = load_script('build_tower_character_index')

    names = module.character_names_from_source(
        '种族圣诞奇莫、黑圣诞奇莫、白圣诞奇莫专属卡牌'
    )

    assert names == ['圣诞奇莫', '黑圣诞奇莫', '白圣诞奇莫']


def test_character_index_links_ability_card_and_mechanics():
    module = load_script('build_tower_character_index')
    entries = [
        {
            'name': '闪耀龙舞',
            'catalog': '天赋图鉴',
            'group': '种族天赋',
            'effect': '使用宝石牌时：获得1层[龙舞]',
            'source': '龙妹奇莫种族天赋',
        },
        {
            'name': '龙宝撞击',
            'catalog': '卡牌图鉴',
            'group': '超越卡牌',
            'type': '超越牌',
            'effect': '[穿透]伤害，卸下1张宝石牌',
            'source': '种族龙妹奇莫专属卡牌',
        },
    ]

    characters = module.build_character_index(entries)

    assert len(characters) == 1
    assert characters[0]['name'] == '龙妹奇莫'
    assert [item['name'] for item in characters[0]['abilities']] == ['闪耀龙舞']
    assert [item['name'] for item in characters[0]['exclusive_cards']] == [
        '龙宝撞击'
    ]
    assert {'超越牌', '宝石牌', '龙舞'} <= set(characters[0]['related_terms'])


def test_merge_catalog_entries_adds_supplements_and_deduplicates_seed_updates():
    module = load_script('build_tower_character_index')
    primary = [
        {'name': '龙木', 'catalog': '卡牌图鉴', 'effect': 'seed version'},
    ]
    supplements = [
        {'name': '龙木', 'catalog': '卡牌图鉴', 'effect': 'supplement version'},
        {
            'name': '献祭',
            'catalog': '卡牌图鉴',
            'effect': 'official balance update',
            'override': True,
        },
        {'name': '天地', 'catalog': '天赋图鉴', 'effect': 'supplement talent'},
    ]
    primary.append(
        {'name': '献祭', 'catalog': '卡牌图鉴', 'effect': 'stale seed version'}
    )

    merged = module.merge_catalog_entries(primary, supplements)

    assert [(entry['catalog'], entry['name']) for entry in merged] == [
        ('卡牌图鉴', '龙木'),
        ('卡牌图鉴', '献祭'),
        ('天赋图鉴', '天地'),
    ]
    assert merged[0]['effect'] == 'seed version'
    assert merged[1]['effect'] == 'official balance update'


def test_character_index_builds_character_from_official_supplements():
    module = load_script('build_tower_character_index')
    entries = [
        {
            'name': '天地',
            'catalog': '天赋图鉴',
            'group': '种族天赋',
            'effect': '使用非超越牌时获得[龙鳞]',
            'source': '白龙奇莫种族天赋',
        },
        {
            'name': '龙木',
            'catalog': '卡牌图鉴',
            'group': '超越卡牌',
            'type': '超越牌',
            'effect': '添加[毒龙]和[中毒]，[移除]',
            'source': '种族白龙奇莫专属卡牌',
        },
    ]

    characters = module.build_character_index(entries)

    assert len(characters) == 1
    assert characters[0]['name'] == '白龙奇莫'
    assert [item['name'] for item in characters[0]['abilities']] == ['天地']
    assert [item['name'] for item in characters[0]['exclusive_cards']] == ['龙木']


def test_ranker_rewards_setup_engine_and_penalizes_unpaid_health_cost():
    module = load_script('rank_tower_choices')
    instant_engine = {
        'name': '迅捷宝石',
        'catalog': '卡牌图鉴',
        'group': '宝石卡牌',
        'type': '宝石牌',
        'effect': '使用[瞬发]牌时：抽1张牌',
    }
    health_cost = {
        'name': '舍命一击',
        'catalog': '卡牌图鉴',
        'group': '战士卡牌',
        'type': '物攻牌',
        'effect': '物理伤害：20，减少自身2点生命',
    }

    instant_score, _ = module.score_entry(instant_engine, '瞬发 宝石牌', None)
    health_score, _ = module.score_entry(health_cost, '瞬发 宝石牌', None)

    assert instant_score > health_score
    assert health_score < 0


def test_ranker_mitigates_health_cost_when_setup_has_repeatable_payoff():
    module = load_script('rank_tower_choices')
    health_cost = {
        'name': '舍命一击',
        'catalog': '卡牌图鉴',
        'group': '战士卡牌',
        'type': '物攻牌',
        'effect': '物理伤害：20，减少自身2点生命',
    }

    plain_score, _ = module.score_entry(health_cost, '', None)
    payoff_score, reasons = module.score_entry(
        health_cost, '生命减少时获得龙骨并恢复生命', None
    )

    assert payoff_score > plain_score
    assert any('mitigated by setup payoff' in reason for reason in reasons)
