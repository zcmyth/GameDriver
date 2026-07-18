import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path


def load_script():
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(
        'simulate_tower_witch', scripts / 'simulate_tower_witch.py'
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_burst_and_giant_steady_state_are_closed():
    module = load_script()

    burst = module.closure_report('burst')
    giant = module.closure_report('giant')

    assert burst.closed is True
    assert burst.net_mana == 1
    assert burst.total_draws == 7
    assert burst.cycle_cards == 6
    assert burst.minimum_starting_mana == 0
    assert burst.ending_mana == 1
    assert giant.closed is True
    assert giant.net_mana == 1
    assert giant.total_draws == 7
    assert giant.cycle_cards == 7
    assert giant.minimum_starting_mana == 0
    assert giant.ending_mana == 1


def test_resource_closure_requires_seven_max_mana_and_three_gems():
    module = load_script()

    assert module.closure_report('burst', max_mana=6).closed is False
    assert (
        module.closure_report('burst', transcend_gems=2).closed is False
    )

    interrupted = module.simulate(
        module.SimulationConfig(enemy_hp=1_000_000, max_mana=6)
    )
    assert interrupted.interrupted_reason == '宝石手套III需要3法力，当前只有2'

    comparisons = module.compare_professions(
        module.SimulationConfig(enemy_hp=10_000, max_mana=6)
    )
    assert module._verdict(comparisons) == '双方中断'

    steady = module.simulate(
        module.SimulationConfig(enemy_hp=1_000_000, max_cycles=2)
    )
    assert steady.interrupted_reason is None
    assert steady.mana == 1

    without_hourglass = module.closure_report(
        'burst', time_hourglass=False
    )
    assert without_hourglass.closed is True
    assert without_hourglass.net_mana == 0
    assert without_hourglass.ending_mana == 0


def test_mage_gets_five_knowledge_per_max_mana():
    module = load_script()
    traveler = module.SimulationConfig(
        profession='traveler', max_mana=7, base_knowledge=20
    )
    mage = replace(traveler, profession='mage')

    assert traveler.initial_knowledge == 20
    assert mage.initial_knowledge == 55


def test_plant_essence_preserves_poison_and_halves_trigger_damage():
    module = load_script()
    config = module.SimulationConfig(enemy_hp=100_000)
    state = module.CombatState(
        enemy_hp=100_000,
        enemy_max_hp=100_000,
        player_hp=1_000,
        player_max_hp=1_000,
        knowledge=0,
        poison=101,
    )

    triggered = module._trigger_poison(state, config)

    assert triggered == 101
    assert state.poison == 101
    assert state.enemy_hp == 99_950


def test_magic_mask_reuses_potent_poison_and_pacifier_counts_both_uses():
    module = load_script()
    config = module.SimulationConfig(
        variant='giant',
        base_knowledge=0,
        enemy_hp=1_000_000,
    )
    state = module.CombatState(
        enemy_hp=1_000_000,
        enemy_max_hp=1_000_000,
        player_hp=1_000,
        player_max_hp=1_000,
        knowledge=0,
        poison=10,
        mana=4,
    )

    module._play_potent_poison(state, config)

    assert state.poison == 40
    assert state.knowledge == 2
    assert state.counters.resolved_card_uses == 2
    assert state.counters.manual_plays == 1
    assert state.counters.mask_reuses == 1


def test_giant_protocol_creates_more_actual_healing_room():
    module = load_script()
    common = module.SimulationConfig(
        profession='traveler',
        enemy_hp=1_000_000,
        max_cycles=1,
        knowledge_model='fixed-additions',
    )

    burst = module.simulate(replace(common, variant='burst'))
    giant = module.simulate(replace(common, variant='giant'))

    assert giant.counters.healing > burst.counters.healing
    assert giant.counters.black_myth_damage > burst.counters.black_myth_damage
    assert giant.player_max_hp == burst.player_max_hp + 300


def test_mage_is_never_slower_than_traveler_with_identical_components():
    module = load_script()

    for enemy_hp in (1_000, 10_000, 50_000, 100_000):
        for variant in module.VARIANTS:
            for knowledge_model in module.KNOWLEDGE_MODELS:
                for rounding in module.ROUNDING_MODES:
                    config = module.SimulationConfig(
                        enemy_hp=enemy_hp,
                        variant=variant,
                        knowledge_model=knowledge_model,
                        rounding=rounding,
                    )
                    results = module.compare_professions(config)
                    traveler = results['traveler']
                    mage = results['mage']

                    assert mage.killed or not traveler.killed
                    if mage.killed and traveler.killed:
                        assert mage.cycles <= traveler.cycles
                        assert (
                            mage.counters.manual_plays
                            <= traveler.counters.manual_plays
                        )


def test_poison_never_exceeds_game_cap():
    module = load_script()
    result = module.simulate(
        module.SimulationConfig(
            enemy_hp=1_000_000,
            max_cycles=5,
            knowledge_model='all-deltas',
        )
    )

    assert result.poison == 9_999


def test_catalog_validation_detects_changed_card_text(tmp_path):
    module = load_script()
    entries = [
        {
            'name': name,
            'cost': '\n'.join(snippets),
            'effect': '\n'.join(snippets),
        }
        for name, snippets in module.CATALOG_EXPECTATIONS.items()
    ]
    catalog = tmp_path / 'catalog.json'
    catalog.write_text(json.dumps(entries))

    assert module.validate_catalog(catalog) == []

    entries[0]['effect'] = '规则已经改变'
    entries[0]['cost'] = ''
    catalog.write_text(json.dumps(entries))

    assert module.validate_catalog(catalog)[0].startswith('献祭:')
