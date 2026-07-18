#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

PROFESSIONS = ('traveler', 'mage')
VARIANTS = ('burst', 'giant')
KNOWLEDGE_MODELS = ('fixed-additions', 'all-deltas')
ROUNDING_MODES = ('floor', 'nearest', 'ceil')
PROFESSION_LABELS = {'traveler': '旅行者', 'mage': '法师'}
VARIANT_LABELS = {'burst': '剧毒速爆', 'giant': '巨人回血'}
KNOWLEDGE_MODEL_LABELS = {
    'fixed-additions': '保守添加',
    'all-deltas': '全部增量',
}
DEFAULT_CATALOG = Path(
    '/Users/chunzhang/games/skills/game-tower/guide/taptap_search_index.json'
)
CATALOG_EXPECTATIONS = {
    '献祭': (
        '0法力值',
        '获得2/3/4点法力',
        '抽1/2/3张牌，[移除]',
    ),
    '毒死': ('3法力值', '添加10/15/20层[中毒]', '触发[中毒]伤害'),
    '烈性毒药': ('4/3/2法力值', '[中毒]层数翻倍'),
    '安乐毒药': ('3法力值', '每触发2层中毒', '回复1点/2点/3点生命'),
    '宝石手套': ('3法力值', '抽牌堆中的1/2/3张宝石牌'),
    '超越宝石': ('使用超越牌时：获得1点法力',),
    '无限宝石': ('卡牌类型与上1张不同时：抽1张牌',),
    '剧毒晶石': ('每对敌方添加3层[中毒]', '额外添加1/2/3层[中毒]'),
    '黑神话': ('每恢复5点生命', '减少敌方1/2/3点生命'),
    '巨人协议': ('增加100/200/300点生命上限',),
    '龙影': ('效果伤害：16', '抽1张牌', '[瞬发]'),
    '魔法面具': ('法力消耗大于等于4点', '将其再次使用'),
    '时之沙漏': ('使用[瞬发]牌时：获得1点法力',),
    '巨人之花': ('生命回复效果增加50%',),
    '机智奶嘴': ('每使用1张技能牌：增加1点[知识]',),
    '你的影子': ('不足12张', '填充[龙影]至12张牌'),
    '牛脾气': ('不会被[移除]', '减少自身1%生命上限'),
    '植物精华': ('[中毒]层数不再衰退', '伤害效果减半'),
}


@dataclass(frozen=True)
class SimulationConfig:
    profession: str = 'traveler'
    variant: str = 'burst'
    knowledge_model: str = 'fixed-additions'
    rounding: str = 'floor'
    enemy_hp: int = 10_000
    player_max_hp: int = 1_000
    player_hp: int | None = None
    max_mana: int = 7
    base_knowledge: int = 20
    max_cycles: int = 20
    poison_cap: int = 9_999
    transcend_gems: int = 3
    time_hourglass: bool = True
    bull_cost_percent: int = 1
    smart_pacifier: bool = True
    giant_flower: bool = True
    plant_essence: bool = True
    magic_mask: bool = True
    black_myth: bool = True
    overheal_counts: bool = False
    witch_revival: bool = True

    def __post_init__(self) -> None:
        if self.profession not in PROFESSIONS:
            raise ValueError(f'unknown profession: {self.profession}')
        if self.variant not in VARIANTS:
            raise ValueError(f'unknown variant: {self.variant}')
        if self.knowledge_model not in KNOWLEDGE_MODELS:
            raise ValueError(f'unknown knowledge model: {self.knowledge_model}')
        if self.rounding not in ROUNDING_MODES:
            raise ValueError(f'unknown rounding mode: {self.rounding}')
        if min(self.enemy_hp, self.player_max_hp, self.max_mana) <= 0:
            raise ValueError('health and max mana must be positive')
        if self.max_cycles <= 0 or self.poison_cap <= 0:
            raise ValueError('max cycles and poison cap must be positive')
        if not 0 <= self.transcend_gems <= 3:
            raise ValueError('transcend gems must be between 0 and 3')
        if self.player_hp is not None and self.player_hp <= 0:
            raise ValueError('player health must be positive')

    @property
    def initial_player_hp(self) -> int:
        return min(self.player_hp or self.player_max_hp, self.player_max_hp)

    @property
    def initial_knowledge(self) -> int:
        mage_bonus = self.max_mana * 5 if self.profession == 'mage' else 0
        return self.base_knowledge + mage_bonus

    @property
    def has_virulent_crystal(self) -> bool:
        return self.variant == 'burst'


@dataclass
class Counters:
    manual_plays: int = 0
    resolved_card_uses: int = 0
    mask_reuses: int = 0
    poison_added: int = 0
    crystal_triggers: int = 0
    poison_triggers: int = 0
    poison_damage: int = 0
    black_myth_damage: int = 0
    dragon_shadow_damage: int = 0
    healing: int = 0
    nominal_healing: int = 0
    bull_damage: int = 0
    sacrifice_damage: int = 0


@dataclass
class CombatState:
    enemy_hp: int
    enemy_max_hp: int
    player_hp: int
    player_max_hp: int
    knowledge: int
    poison: int = 0
    mana: int = 0
    dead: bool = False
    revival_used: bool = False
    interrupted_reason: str | None = None
    counters: Counters = field(default_factory=Counters)


@dataclass(frozen=True)
class CycleTrace:
    cycle: int
    enemy_hp_start: int
    enemy_hp_end: int
    player_hp_start: int
    player_hp_end: int
    player_max_hp_start: int
    player_max_hp_end: int
    poison_start: int
    poison_end: int
    knowledge_start: int
    knowledge_end: int
    mana_start: int
    mana_end: int
    manual_plays: int
    resolved_card_uses: int
    poison_damage: int
    black_myth_damage: int
    dragon_shadow_damage: int
    healing: int


@dataclass(frozen=True)
class ClosureReport:
    variant: str
    max_mana: int
    cycle_cards: int
    resolved_card_uses: int
    intrinsic_draws: int
    infinite_gem_draws: int
    total_draws: int
    draw_surplus: int
    net_mana: int
    minimum_starting_mana: int | None
    ending_mana: int | None
    closed: bool


@dataclass(frozen=True)
class SimulationResult:
    config: SimulationConfig
    killed: bool
    player_survived: bool
    cycles: int
    enemy_hp_remaining: int
    player_hp: int
    player_max_hp: int
    poison: int
    knowledge: int
    mana: int
    revival_used: bool
    interrupted_reason: str | None
    counters: Counters
    closure: ClosureReport
    traces: tuple[CycleTrace, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload['traces'] = [asdict(trace) for trace in self.traces]
        return payload


def validate_catalog(path: Path) -> list[str]:
    payload = json.loads(path.read_text())
    entries = payload.get('entries', []) if isinstance(payload, dict) else payload
    by_name = {
        str(entry.get('name')): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get('name')
    }
    errors = []
    for name, snippets in CATALOG_EXPECTATIONS.items():
        entry = by_name.get(name)
        if entry is None:
            errors.append(f'{name}: catalog entry missing')
            continue
        text = '\n'.join(
            str(entry.get(field) or '') for field in ('cost', 'effect')
        )
        missing = [snippet for snippet in snippets if snippet not in text]
        if missing:
            errors.append(f'{name}: missing expected text {missing}')
    return errors


def round_ratio(value: int, numerator: int, denominator: int, mode: str) -> int:
    scaled = value * numerator
    if mode == 'floor':
        return scaled // denominator
    if mode == 'ceil':
        return (scaled + denominator - 1) // denominator
    return (scaled + denominator // 2) // denominator


def scale_mark(layers: int, knowledge: int, mode: str) -> int:
    return round_ratio(layers, 100 + knowledge, 100, mode)


@dataclass(frozen=True)
class ResourceCard:
    name: str
    card_type: str
    cost: int
    mana_gain: int
    draws: int
    manual: bool


def _resource_cards(
    variant: str,
    *,
    transcend_gems: int,
    time_hourglass: bool,
) -> tuple[ResourceCard, ...]:
    hourglass = int(time_hourglass)
    transcend_refund = transcend_gems
    if variant == 'burst':
        cards = (
            ResourceCard(
                '献祭III',
                'transcend',
                0,
                4 + transcend_refund,
                3,
                True,
            ),
            ResourceCard(
                '毒死III', 'transcend', 3, transcend_refund, 0, True
            ),
            ResourceCard('烈性毒药I', 'skill', 4, 0, 0, True),
            ResourceCard(
                '烈性毒药I/魔法面具', 'skill', 0, 0, 0, False
            ),
            ResourceCard(
                '宝石手套III', 'transcend', 3, transcend_refund, 0, True
            ),
            ResourceCard(
                '龙影',
                'transcend',
                3,
                transcend_refund + hourglass,
                1,
                True,
            ),
            ResourceCard('安乐毒药III', 'skill', 3, 0, 0, True),
        )
    else:
        cards = (
            ResourceCard(
                '献祭III',
                'transcend',
                0,
                4 + transcend_refund,
                3,
                True,
            ),
            ResourceCard(
                '毒死III', 'transcend', 3, transcend_refund, 0, True
            ),
            ResourceCard('烈性毒药I', 'skill', 4, 0, 0, True),
            ResourceCard(
                '烈性毒药I/魔法面具', 'skill', 0, 0, 0, False
            ),
            ResourceCard(
                '巨人协议III', 'transcend', 3, transcend_refund, 0, True
            ),
            ResourceCard(
                '宝石手套III', 'transcend', 3, transcend_refund, 0, True
            ),
            ResourceCard(
                '龙影',
                'transcend',
                3,
                transcend_refund + hourglass,
                1,
                True,
            ),
            ResourceCard('安乐毒药III', 'skill', 3, 0, 0, True),
        )
    return cards


def closure_report(
    variant: str,
    max_mana: int = 7,
    transcend_gems: int = 3,
    time_hourglass: bool = True,
) -> ClosureReport:
    if variant not in VARIANTS:
        raise ValueError(f'unknown variant: {variant}')
    if max_mana <= 0:
        raise ValueError('max mana must be positive')
    if not 0 <= transcend_gems <= 3:
        raise ValueError('transcend gems must be between 0 and 3')
    cards = _resource_cards(
        variant,
        transcend_gems=transcend_gems,
        time_hourglass=time_hourglass,
    )

    intrinsic_draws = 0
    infinite_draws = 0
    previous_type = None
    for card in cards:
        intrinsic_draws += card.draws
        if previous_type is not None and card.card_type != previous_type:
            infinite_draws += 1
        previous_type = card.card_type

    cycle_cards = sum(card.manual for card in cards)
    total_draws = intrinsic_draws + infinite_draws
    net_mana = sum(card.mana_gain - card.cost for card in cards)
    minimum_starting_mana = None
    ending_mana = None
    for starting_mana in range(max_mana + 1):
        mana = starting_mana
        for card in cards:
            if mana < card.cost:
                break
            mana -= card.cost
            mana = min(max_mana, mana + card.mana_gain)
        else:
            minimum_starting_mana = starting_mana
            ending_mana = mana
            break

    return ClosureReport(
        variant=variant,
        max_mana=max_mana,
        cycle_cards=cycle_cards,
        resolved_card_uses=len(cards),
        intrinsic_draws=intrinsic_draws,
        infinite_gem_draws=infinite_draws,
        total_draws=total_draws,
        draw_surplus=total_draws - cycle_cards,
        net_mana=net_mana,
        minimum_starting_mana=minimum_starting_mana,
        ending_mana=ending_mana,
        closed=(
            minimum_starting_mana is not None
            and ending_mana is not None
            and ending_mana >= minimum_starting_mana
            and net_mana >= 0
            and total_draws >= cycle_cards
        ),
    )


def _counter_delta(after: Counters, before: Counters, field_name: str) -> int:
    return getattr(after, field_name) - getattr(before, field_name)


def _record_use(state: CombatState, *, manual: bool, mask_reuse: bool = False) -> None:
    state.counters.resolved_card_uses += 1
    if manual:
        state.counters.manual_plays += 1
    if mask_reuse:
        state.counters.mask_reuses += 1


def _spend_mana(state: CombatState, amount: int, card_name: str) -> bool:
    if state.mana < amount:
        state.interrupted_reason = (
            f'{card_name}需要{amount}法力，当前只有{state.mana}'
        )
        return False
    state.mana -= amount
    return True


def _gain_mana(
    state: CombatState,
    amount: int,
    config: SimulationConfig,
) -> None:
    state.mana = min(config.max_mana, state.mana + amount)


def _transcend_refund(
    state: CombatState,
    config: SimulationConfig,
    *,
    instant: bool = False,
) -> None:
    refund = config.transcend_gems
    if instant and config.time_hourglass:
        refund += 1
    _gain_mana(state, refund, config)


def _deal_enemy_damage(state: CombatState, amount: int, source: str) -> None:
    if amount <= 0 or state.enemy_hp <= 0:
        return
    actual = min(amount, state.enemy_hp)
    state.enemy_hp -= actual
    if source == 'poison':
        state.counters.poison_damage += actual
    elif source == 'black_myth':
        state.counters.black_myth_damage += actual
    elif source == 'dragon_shadow':
        state.counters.dragon_shadow_damage += actual


def _lose_health(state: CombatState, amount: int, config: SimulationConfig) -> None:
    if amount <= 0 or state.dead:
        return
    state.player_hp -= amount
    if state.player_hp > 0:
        return
    if config.witch_revival and not state.revival_used:
        state.revival_used = True
        state.player_hp = max(1, state.player_max_hp // 5)
        return
    state.player_hp = 0
    state.dead = True


def _apply_bull(state: CombatState, config: SimulationConfig) -> None:
    cost = max(1, state.player_max_hp * config.bull_cost_percent // 100)
    state.counters.bull_damage += cost
    _lose_health(state, cost, config)


def _add_poison(
    state: CombatState,
    layers: int,
    config: SimulationConfig,
    *,
    scalable_delta: bool,
) -> None:
    if layers <= 0 or state.poison >= config.poison_cap:
        return

    primary = (
        scale_mark(layers, state.knowledge, config.rounding)
        if scalable_delta
        else layers
    )
    primary = min(primary, config.poison_cap - state.poison)
    state.poison += primary
    state.counters.poison_added += primary

    if not config.has_virulent_crystal or primary < 3:
        return
    triggers = primary // 3
    bonus_per_trigger = scale_mark(3, state.knowledge, config.rounding)
    bonus = min(
        triggers * bonus_per_trigger,
        config.poison_cap - state.poison,
    )
    state.poison += bonus
    state.counters.poison_added += bonus
    state.counters.crystal_triggers += triggers


def _trigger_poison(state: CombatState, config: SimulationConfig) -> int:
    triggered_layers = state.poison
    damage = triggered_layers
    if config.plant_essence:
        damage //= 2
    else:
        state.poison //= 2
    state.counters.poison_triggers += 1
    _deal_enemy_damage(state, damage, 'poison')
    return triggered_layers


def _play_sacrifice(state: CombatState, config: SimulationConfig) -> None:
    _record_use(state, manual=True)
    _gain_mana(state, 4, config)
    _transcend_refund(state, config)
    state.counters.sacrifice_damage += 8
    _lose_health(state, 8, config)
    if not state.dead:
        _apply_bull(state, config)


def _play_toxic_death(state: CombatState, config: SimulationConfig) -> None:
    if not _spend_mana(state, 3, '毒死III'):
        return
    _record_use(state, manual=True)
    _transcend_refund(state, config)
    _add_poison(state, 20, config, scalable_delta=True)
    _trigger_poison(state, config)
    if state.enemy_hp > 0:
        _apply_bull(state, config)


def _play_potent_poison_once(
    state: CombatState,
    config: SimulationConfig,
    *,
    manual: bool,
) -> None:
    _record_use(state, manual=manual, mask_reuse=not manual)
    if config.smart_pacifier:
        state.knowledge += 1
    delta = state.poison
    _add_poison(
        state,
        delta,
        config,
        scalable_delta=config.knowledge_model == 'all-deltas',
    )
    _apply_bull(state, config)


def _play_potent_poison(state: CombatState, config: SimulationConfig) -> None:
    if not _spend_mana(state, 4, '烈性毒药I'):
        return
    _play_potent_poison_once(state, config, manual=True)
    if config.magic_mask and not state.dead:
        _play_potent_poison_once(state, config, manual=False)


def _play_giant_protocol(state: CombatState, config: SimulationConfig) -> None:
    if not _spend_mana(state, 3, '巨人协议III'):
        return
    _record_use(state, manual=True)
    _transcend_refund(state, config)
    state.player_max_hp += 300
    _apply_bull(state, config)


def _play_euthanasia(state: CombatState, config: SimulationConfig) -> None:
    if not _spend_mana(state, 3, '安乐毒药III'):
        return
    _record_use(state, manual=True)
    if config.smart_pacifier:
        state.knowledge += 1
    triggered_layers = _trigger_poison(state, config)
    if state.enemy_hp <= 0:
        return

    nominal_healing = (triggered_layers // 2) * 3
    if config.giant_flower:
        nominal_healing = round_ratio(
            nominal_healing,
            3,
            2,
            config.rounding,
        )
    missing_health = state.player_max_hp - state.player_hp
    actual_healing = min(nominal_healing, missing_health)
    state.player_hp += actual_healing
    state.counters.healing += actual_healing
    state.counters.nominal_healing += nominal_healing

    counted_healing = nominal_healing if config.overheal_counts else actual_healing
    black_myth_damage = counted_healing // 5 * 3 if config.black_myth else 0
    _deal_enemy_damage(state, black_myth_damage, 'black_myth')
    if state.enemy_hp > 0:
        _apply_bull(state, config)


def _play_gem_glove(state: CombatState, config: SimulationConfig) -> None:
    if not _spend_mana(state, 3, '宝石手套III'):
        return
    _record_use(state, manual=True)
    _transcend_refund(state, config)
    _apply_bull(state, config)


def _play_dragon_shadow(state: CombatState, config: SimulationConfig) -> None:
    if not _spend_mana(state, 3, '龙影'):
        return
    _record_use(state, manual=True)
    _transcend_refund(state, config, instant=True)
    damage = round_ratio(16, 120, 100, config.rounding)
    _deal_enemy_damage(state, damage, 'dragon_shadow')


def _take_trace(
    cycle: int,
    state: CombatState,
    before_state: tuple[int, int, int, int, int, int],
    before_counters: Counters,
) -> CycleTrace:
    (
        enemy_hp,
        player_hp,
        player_max_hp,
        poison,
        knowledge,
        mana,
    ) = before_state
    return CycleTrace(
        cycle=cycle,
        enemy_hp_start=enemy_hp,
        enemy_hp_end=state.enemy_hp,
        player_hp_start=player_hp,
        player_hp_end=state.player_hp,
        player_max_hp_start=player_max_hp,
        player_max_hp_end=state.player_max_hp,
        poison_start=poison,
        poison_end=state.poison,
        knowledge_start=knowledge,
        knowledge_end=state.knowledge,
        mana_start=mana,
        mana_end=state.mana,
        manual_plays=_counter_delta(
            state.counters, before_counters, 'manual_plays'
        ),
        resolved_card_uses=_counter_delta(
            state.counters, before_counters, 'resolved_card_uses'
        ),
        poison_damage=_counter_delta(
            state.counters, before_counters, 'poison_damage'
        ),
        black_myth_damage=_counter_delta(
            state.counters, before_counters, 'black_myth_damage'
        ),
        dragon_shadow_damage=_counter_delta(
            state.counters, before_counters, 'dragon_shadow_damage'
        ),
        healing=_counter_delta(state.counters, before_counters, 'healing'),
    )


def simulate(config: SimulationConfig) -> SimulationResult:
    state = CombatState(
        enemy_hp=config.enemy_hp,
        enemy_max_hp=config.enemy_hp,
        player_hp=config.initial_player_hp,
        player_max_hp=config.player_max_hp,
        knowledge=config.initial_knowledge,
    )
    traces: list[CycleTrace] = []

    for cycle in range(1, config.max_cycles + 1):
        before_state = (
            state.enemy_hp,
            state.player_hp,
            state.player_max_hp,
            state.poison,
            state.knowledge,
            state.mana,
        )
        before_counters = replace(state.counters)

        _play_sacrifice(state, config)
        if not state.dead and state.interrupted_reason is None:
            _play_toxic_death(state, config)
        if (
            not state.dead
            and state.enemy_hp > 0
            and state.interrupted_reason is None
        ):
            _play_potent_poison(state, config)
        if (
            config.variant == 'giant'
            and not state.dead
            and state.enemy_hp > 0
            and state.interrupted_reason is None
        ):
            _play_giant_protocol(state, config)
        if (
            not state.dead
            and state.enemy_hp > 0
            and state.interrupted_reason is None
        ):
            _play_gem_glove(state, config)
        if (
            not state.dead
            and state.enemy_hp > 0
            and state.interrupted_reason is None
        ):
            _play_dragon_shadow(state, config)
        if (
            not state.dead
            and state.enemy_hp > 0
            and state.interrupted_reason is None
        ):
            _play_euthanasia(state, config)

        traces.append(
            _take_trace(cycle, state, before_state, before_counters)
        )
        if state.dead or state.enemy_hp <= 0 or state.interrupted_reason:
            break

    return SimulationResult(
        config=config,
        killed=state.enemy_hp <= 0,
        player_survived=not state.dead,
        cycles=len(traces),
        enemy_hp_remaining=state.enemy_hp,
        player_hp=state.player_hp,
        player_max_hp=state.player_max_hp,
        poison=state.poison,
        knowledge=state.knowledge,
        mana=state.mana,
        revival_used=state.revival_used,
        interrupted_reason=state.interrupted_reason,
        counters=state.counters,
        closure=closure_report(
            config.variant,
            max_mana=config.max_mana,
            transcend_gems=config.transcend_gems,
            time_hourglass=config.time_hourglass,
        ),
        traces=tuple(traces),
    )


def compare_professions(config: SimulationConfig) -> dict[str, SimulationResult]:
    return {
        profession: simulate(replace(config, profession=profession))
        for profession in PROFESSIONS
    }


def _short_result(result: SimulationResult) -> str:
    if result.interrupted_reason:
        status = f'中断({result.interrupted_reason})'
    else:
        status = '击杀' if result.killed else f'剩{result.enemy_hp_remaining}'
    counters = result.counters
    return (
        f'{result.cycles}轮/{counters.manual_plays}手动/'
        f'{counters.resolved_card_uses}结算/{status}'
    )


def _verdict(results: dict[str, SimulationResult]) -> str:
    traveler = results['traveler']
    mage = results['mage']
    if traveler.interrupted_reason and mage.interrupted_reason:
        return '双方中断'
    if traveler.interrupted_reason:
        return '法师闭环'
    if mage.interrupted_reason:
        return '旅行者闭环'
    if mage.killed and not traveler.killed:
        return '法师胜'
    if traveler.killed and not mage.killed:
        return '旅行者胜'
    traveler_key = (
        traveler.interrupted_reason is not None,
        not traveler.killed,
        traveler.cycles,
        traveler.counters.manual_plays,
        traveler.counters.resolved_card_uses,
        traveler.enemy_hp_remaining,
    )
    mage_key = (
        mage.interrupted_reason is not None,
        not mage.killed,
        mage.cycles,
        mage.counters.manual_plays,
        mage.counters.resolved_card_uses,
        mage.enemy_hp_remaining,
    )
    if mage_key < traveler_key:
        return '法师更快'
    if traveler_key < mage_key:
        return '旅行者更快'
    return '同速'


def render_report(
    comparisons: list[tuple[SimulationConfig, dict[str, SimulationResult]]],
    *,
    trace: bool,
) -> str:
    first = comparisons[0][0]
    lines = [
        '女巫毒影职业模拟',
        (
            f'共同参数：基础知识{first.base_knowledge}，法力上限'
            f'{first.max_mana}，初始生命{first.initial_player_hp}/'
            f'{first.player_max_hp}，毒上限{first.poison_cap}，超越宝石'
            f'{first.transcend_gems}颗，时之沙漏'
            f'{"有" if first.time_hourglass else "无"}'
        ),
        '知识模型：保守添加只放大明确增加的印记；全部增量也放大烈性毒药增加的毒层。',
        '',
        '| 敌方生命 | 构筑 | 知识模型 | 旅行者 | 法师 | 结论 |',
        '|---:|---|---|---|---|---|',
    ]
    for config, results in comparisons:
        lines.append(
            f'| {config.enemy_hp} | {VARIANT_LABELS[config.variant]} | '
            f'{KNOWLEDGE_MODEL_LABELS[config.knowledge_model]} | '
            f'{_short_result(results["traveler"])} | '
            f'{_short_result(results["mage"])} | {_verdict(results)} |'
        )

    variants = sorted({config.variant for config, _ in comparisons})
    lines.extend(['', '稳态闭环：'])
    for variant in variants:
        closure = closure_report(
            variant,
            max_mana=first.max_mana,
            transcend_gems=first.transcend_gems,
            time_hourglass=first.time_hourglass,
        )
        starting_mana = (
            str(closure.minimum_starting_mana)
            if closure.minimum_starting_mana is not None
            else '不可启动'
        )
        ending_mana = (
            str(closure.ending_mana)
            if closure.ending_mana is not None
            else '-'
        )
        lines.append(
            f'- {VARIANT_LABELS[variant]}: {closure.cycle_cards}张循环牌，'
            f'{closure.total_draws}次抽牌，净法力{closure.net_mana:+d}，'
            f'最低起始法力{starting_mana}，首轮结束法力{ending_mana}，'
            f'{"闭环" if closure.closed else "会中断"}'
        )

    if trace:
        lines.extend(['', '逐轮明细：'])
        for config, results in comparisons:
            lines.append(
                f'[{config.enemy_hp}/{VARIANT_LABELS[config.variant]}/'
                f'{KNOWLEDGE_MODEL_LABELS[config.knowledge_model]}]'
            )
            for profession, result in results.items():
                lines.append(
                    f'  {PROFESSION_LABELS[profession]}: '
                    f'初始知识{result.config.initial_knowledge}'
                )
                for item in result.traces:
                    dealt = item.enemy_hp_start - item.enemy_hp_end
                    lines.append(
                        f'    轮{item.cycle}: 伤害{dealt}，毒'
                        f'{item.poison_start}->{item.poison_end}，知识'
                        f'{item.knowledge_start}->{item.knowledge_end}，'
                        f'回血{item.healing}，法力{item.mana_start}->{item.mana_end}'
                    )
    return '\n'.join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Simulate the Witch poison-shadow loop by profession.'
    )
    parser.add_argument(
        '--enemy-hp',
        type=int,
        nargs='+',
        default=[1_000, 10_000, 50_000, 100_000],
    )
    parser.add_argument('--variant', choices=(*VARIANTS, 'both'), default='both')
    parser.add_argument(
        '--knowledge-model',
        choices=(*KNOWLEDGE_MODELS, 'both'),
        default='both',
    )
    parser.add_argument('--rounding', choices=ROUNDING_MODES, default='floor')
    parser.add_argument('--max-mana', type=int, default=7)
    parser.add_argument('--base-knowledge', type=int, default=20)
    parser.add_argument('--player-max-hp', type=int, default=1_000)
    parser.add_argument('--player-hp', type=int)
    parser.add_argument('--max-cycles', type=int, default=20)
    parser.add_argument('--poison-cap', type=int, default=9_999)
    parser.add_argument(
        '--transcend-gems',
        type=int,
        choices=range(4),
        default=3,
    )
    parser.add_argument('--no-hourglass', action='store_true')
    parser.add_argument('--overheal-counts', action='store_true')
    parser.add_argument('--no-smart-pacifier', action='store_true')
    parser.add_argument('--no-giant-flower', action='store_true')
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--catalog', type=Path, default=DEFAULT_CATALOG)
    parser.add_argument('--skip-catalog-validation', action='store_true')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_catalog_validation:
        errors = validate_catalog(args.catalog)
        if errors:
            details = '\n'.join(f'- {error}' for error in errors)
            raise SystemExit(f'catalog validation failed:\n{details}')
    variants = VARIANTS if args.variant == 'both' else (args.variant,)
    knowledge_models = (
        KNOWLEDGE_MODELS
        if args.knowledge_model == 'both'
        else (args.knowledge_model,)
    )
    comparisons = []
    for enemy_hp in args.enemy_hp:
        for variant in variants:
            for knowledge_model in knowledge_models:
                config = SimulationConfig(
                    enemy_hp=enemy_hp,
                    variant=variant,
                    knowledge_model=knowledge_model,
                    rounding=args.rounding,
                    max_mana=args.max_mana,
                    base_knowledge=args.base_knowledge,
                    player_max_hp=args.player_max_hp,
                    player_hp=args.player_hp,
                    max_cycles=args.max_cycles,
                    poison_cap=args.poison_cap,
                    transcend_gems=args.transcend_gems,
                    time_hourglass=not args.no_hourglass,
                    overheal_counts=args.overheal_counts,
                    smart_pacifier=not args.no_smart_pacifier,
                    giant_flower=not args.no_giant_flower,
                )
                comparisons.append((config, compare_professions(config)))

    if args.json:
        payload = [
            {
                'config': asdict(config),
                'results': {
                    profession: result.to_dict()
                    for profession, result in results.items()
                },
            }
            for config, results in comparisons
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(render_report(comparisons, trace=args.trace))


if __name__ == '__main__':
    main()
