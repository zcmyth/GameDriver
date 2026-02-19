import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SurvivorStrategy:
    def __init__(self, artifact_dir='artifacts/stuck'):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        self.start_cooldown_until = -1

        self.energy_actions = [
            'steamroll',
            'battle',
        ]

        self.critical_controls = [
            'confirm',
            'next',
            'ok',
            'start',
            'revival',
            'ad',
        ]

        self.free_controls = [
            'activate',
            'confirm',
            'next',
            'ok',
        ]

        self.home_actions = [
            'view',
            'patrol',
            'challenge',
            'friends',
            'chest',
        ]

        self.nav_labels = [
            'main challenge',
            'challenge',
            'patrol',
            'friends',
            'chest',
            'view',
        ]

        self.nav_scan_points = [
            (0.10, 0.86),
            (0.50, 0.90),
        ]

        self.high_risk_patterns = [
            re.compile(r'\bbuy\b'),
            re.compile(r'\bpurchase\b'),
        ]

        self.blocked_texts = [
            'buy now',
            'special offer',
            'limited time',
        ]

        self.popup_markers = [
            'daily pack',
            'weekly pack',
            'monthly pack',
            'part assist pack',
            'gift',
            'sale',
        ]

        self.last_action = None
        self.loop_cycle_hits = 0
        self.loop_stuck_hits = 0
        self.home_last_target = None
        self.home_same_target_count = 0
        self.home_nochange_count = 0
        self.target_unclickable_penalty = {}

        self.low_energy_texts = [
            'not enough energy',
            'insufficient energy',
            'need energy',
            'out of energy',
            'no energy',
        ]

        self.preferred_skills = [
            'destroyer',
            'drone',
            'atk',
            'all ammo',
            'duration',
            'hi-power',
            'energy',
            'bullet',
        ]

        self.secondary_skills = [
            'havoc',
            'starforge',
            'palm',
            'soccer',
            'drill',
            'twinborn',
        ]

        self.skill_alias_patterns = [
            re.compile(r'\batk\b'),
            re.compile(r'all\s*ammo'),
            re.compile(r'hi[- ]?power'),
            re.compile(r'bullet'),
            re.compile(r'energy'),
            re.compile(r'drone'),
            re.compile(r'destroyer'),
            re.compile(r'duration'),
        ]

        self.icon_template_candidates = [
            'templates/survivor/close.png',
            'templates/survivor/skip.png',
            'templates/survivor/confirm.png',
        ]

        # Progress vs activity tracking.
        self.last_signature = None
        self.last_scene_kind = None
        self.no_progress_steps = 0
        self.recovery_attempts = 0
        self.recovery_success = 0

    @staticmethod
    def _text_samples(engine):
        return [item['text'].lower() for item in engine._locations]

    @staticmethod
    def _is_numeric_noise(text):
        return bool(re.fullmatch(r'[0-9:.xbmkn+\- ]{2,}', text.lower()))

    def _emit_decision(self, i, action, decision, reason, detail=''):
        logger.info(
            'event=survivor_decision iter=%s action=%s decision=%s reason=%s detail=%s',
            i,
            action,
            decision,
            reason,
            detail,
        )

    def _contains_high_risk_buy(self, engine):
        for item in engine._locations:
            if item.get('confidence', 0) < 0.93:
                continue
            text = str(item.get('text', '')).lower()
            if any(pattern.search(text) for pattern in self.high_risk_patterns):
                return True
        return False

    def _contains_blocked_purchase_text(self, engine):
        has_purchase_text = self._contains_high_risk_buy(engine) or any(
            engine.contains(text, min_confidence=0.93)
            for text in self.blocked_texts
        )
        if not has_purchase_text:
            return False

        # Avoid false positives from normal progression labels like
        # "unlocked in shop" on chapter cards.
        if engine.contains('unlocked in shop', min_confidence=0.85):
            return False

        # Only treat as blocked when the UI also looks like a popup/offer.
        return any(
            engine.contains(text, min_confidence=0.82)
            for text in self.popup_markers
        )

    def _contains_low_energy_text(self, engine):
        # Skill choice includes terms like "Energy Drink"; avoid false low-energy mode.
        if engine.contains('choice', min_confidence=0.9):
            return False

        return any(
            engine.contains(text, min_confidence=0.85)
            for text in self.low_energy_texts
        )

    def _run_low_energy_fallback(self, engine, i):
        free_targets = self._safe_targets(self.free_controls)
        if engine.click_first_text(free_targets, min_confidence=0.85)[0]:
            return True

        if engine.try_click_text(re.compile(r'\bad\b', re.I), min_confidence=0.85):
            return True

        if engine.try_click_text('reward', min_confidence=0.88):
            return True

        if engine.try_click_text('claim', min_confidence=0.88):
            return True

        if i % 6 == 0:
            engine.click(46.0 / 460, 960.0 / 1024, False)
            return True

        return False

    @staticmethod
    def _safe_targets(targets):
        return [
            t
            for t in targets
            if 'buy' not in t.lower() and 'purchase' not in t.lower()
        ]

    def _try_click_icon_templates(self, engine):
        for template in self.icon_template_candidates:
            try:
                if engine.try_click_template(template, threshold=0.88):
                    return True, template
            except (KeyError, FileNotFoundError, ValueError):
                continue
        return False, None

    def _click_best_text_match(self, engine, targets, min_confidence=0.85, exact=False):
        scored_targets = []

        for target in self._safe_targets(targets):
            matches = engine.get_matched_locations(
                target,
                exact=exact,
                min_confidence=min_confidence,
            )
            if not matches:
                continue
            top = matches[0]
            conf = top.get('confidence', 0)
            penalty = self.target_unclickable_penalty.get(target, 0)
            score = conf - (0.12 * penalty)
            scored_targets.append((score, target))

        if not scored_targets:
            return False, None

        scored_targets.sort(key=lambda item: item[0], reverse=True)
        ordered_targets = [target for _, target in scored_targets]

        result = engine.click_targets_until_changed(
            ordered_targets,
            min_confidence=min_confidence,
            exact=exact,
            verify_wait_s=0.8,
            max_candidates_per_target=1,
        )

        for attempt in result.get('details', []):
            target = attempt.get('target')
            if not target or not attempt.get('matched') or not attempt.get('clicked'):
                continue
            if attempt.get('state_changed'):
                self.target_unclickable_penalty[target] = max(
                    0, self.target_unclickable_penalty.get(target, 0) - 1
                )
            else:
                self.target_unclickable_penalty[target] = min(
                    6, self.target_unclickable_penalty.get(target, 0) + 1
                )

        if result.get('success'):
            return True, result.get('clicked_target')
        return False, None

    def _try_click_critical_controls(self, engine, i=None):
        safe_critical = self._safe_targets(self.critical_controls)
        if i is not None and i < self.start_cooldown_until:
            safe_critical = [c for c in safe_critical if c != 'start']
        return self._click_best_text_match(
            engine,
            safe_critical,
            min_confidence=0.85,
            exact=True,
        )

    def _try_click_nav_labels(self, engine):
        safe_nav = self._safe_targets(self.nav_labels)
        return self._click_best_text_match(
            engine,
            safe_nav,
            min_confidence=0.82,
            exact=False,
        )

    def _try_click_skill_alias(self, engine, min_confidence=0.88):
        for item in engine._locations:
            if item.get('confidence', 0) < min_confidence:
                continue
            text = str(item.get('text', '')).lower()
            if any(pattern.search(text) for pattern in self.skill_alias_patterns):
                engine.click(item['x'], item['y'], wait=False)
                engine.wait(0.6)
                if not engine.contains('choice', min_confidence=0.9):
                    return True, text
        return False, None

    def _try_click_skill_targets(self, engine, targets, min_confidence=0.88):
        for target in self._safe_targets(targets):
            matches = engine.get_matched_locations(
                target,
                min_confidence=min_confidence,
            )
            if not matches:
                continue

            hit = matches[0]
            engine.click(hit['x'], hit['y'], wait=False)
            engine.wait(0.6)
            if not engine.contains('choice', min_confidence=0.9):
                return True, target

            engine.click(hit['x'], min(hit['y'] + 0.08, 0.95), wait=False)
            engine.wait(0.6)
            if not engine.contains('choice', min_confidence=0.9):
                return True, target

        return self._try_click_skill_alias(engine, min_confidence=min_confidence)

    def _force_alternate_recovery(self, engine, i, reason):
        # Stronger path to break repeated home-scene target loops.
        engine.click(46.0 / 460, 960.0 / 1024, False)  # back
        engine.click(0.50, 0.10, False)                # top-center dismiss
        engine.click(0.10, 0.86, False)                # challenge area
        engine.click(0.50, 0.90, False)                # bottom nav center
        self._emit_decision(i, 'alternate_recovery', 'fallback', reason)

    def _record_home_click_outcome(self, target, before_sig, engine, i):
        # Verify post-click state change when on home scene.
        engine.wait(0.8)
        after = engine.recent_signatures(1)
        after_sig = after[-1] if after else ''
        changed = bool(before_sig and after_sig and before_sig != after_sig)

        if target == self.home_last_target:
            self.home_same_target_count += 1
        else:
            self.home_last_target = target
            self.home_same_target_count = 1

        if changed:
            self.home_nochange_count = 0
            self.target_unclickable_penalty[target] = max(
                0, self.target_unclickable_penalty.get(target, 0) - 1
            )
        else:
            self.home_nochange_count += 1
            self.target_unclickable_penalty[target] = min(
                6, self.target_unclickable_penalty.get(target, 0) + 1
            )

        self._emit_decision(
            i,
            target,
            'state_changed' if changed else 'state_unchanged',
            'post_click_signature_check',
            detail=f'same_target_count={self.home_same_target_count} nochange_count={self.home_nochange_count}',
        )

        if self.home_same_target_count >= 4 and self.home_nochange_count >= 3:
            self._force_alternate_recovery(engine, i, 'same_target_nochange_loop')
            self.home_same_target_count = 0
            self.home_nochange_count = 0
            self.home_last_target = None
            return False

        return True

    def _is_in_battle(self, engine):
        texts = self._text_samples(engine)
        if not texts:
            return False

        numeric_noise = sum(1 for text in texts if self._is_numeric_noise(text))
        has_timer = any(':' in text for text in texts)
        has_level = any('lv.' in text for text in texts)
        return (numeric_noise >= 8 and has_timer) or (numeric_noise >= 6 and has_level)

    def _scene_kind(self, engine):
        if engine.contains('choice', min_confidence=0.9):
            return 'skill_choice'
        if self._is_in_battle(engine):
            return 'battle'
        if self._contains_blocked_purchase_text(engine):
            return 'offer_popup'
        if any(
            engine.contains(text, min_confidence=0.85)
            for text in ('mission', 'patrol', 'friends', 'challenge', 'start')
        ):
            return 'home'
        return 'unknown'

    def _track_progress_signals(self, engine, i):
        recent = engine.recent_signatures(1)
        current_sig = recent[-1] if recent else None
        current_scene = self._scene_kind(engine)

        signature_changed = bool(
            self.last_signature and current_sig and self.last_signature != current_sig
        )
        scene_changed = bool(
            self.last_scene_kind and self.last_scene_kind != current_scene
        )

        progressed = signature_changed or scene_changed
        if progressed:
            self.no_progress_steps = 0
        else:
            self.no_progress_steps += 1

        self.last_signature = current_sig
        self.last_scene_kind = current_scene

        if self.no_progress_steps > 0 and self.no_progress_steps % 10 == 0:
            logger.warning(
                'No-progress streak steps=%s scene=%s iter=%s recoveries=%s/%s',
                self.no_progress_steps,
                current_scene,
                i,
                self.recovery_success,
                self.recovery_attempts,
            )

        return current_scene

    def step(self, engine, i):
        current_scene = self._track_progress_signals(engine, i)

        if self.no_progress_steps >= 14:
            self._emit_decision(
                i,
                'no_progress_guard',
                'fallback',
                'streak_breaker',
                detail=f'scene={current_scene} steps={self.no_progress_steps}',
            )
            self._force_alternate_recovery(engine, i, 'no_progress_guard')
            self.no_progress_steps = 0
            return

        hard_stuck = engine.is_stuck(repeat_threshold=8)
        cycle_stuck = engine.is_cycle_stuck(cycle_len=2, min_cycles=3)

        if hard_stuck:
            self.loop_stuck_hits += 1
        else:
            self.loop_stuck_hits = 0

        if cycle_stuck:
            self.loop_cycle_hits += 1
        else:
            self.loop_cycle_hits = 0

        if hard_stuck or cycle_stuck:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            debug_path = self.artifact_dir / f'stuck_{ts}.png'
            engine.debug().save(debug_path)

            before = engine.recent_signatures(1)
            before_sig = before[-1] if before else ''
            self.recovery_attempts += 1

            if self.loop_cycle_hits >= 3 or self.loop_stuck_hits >= 3:
                logger.warning(
                    'Detected persistent loop (hard_stuck=%s cycle_stuck=%s) '
                    'saved=%s escalating recovery',
                    hard_stuck,
                    cycle_stuck,
                    debug_path,
                )
                # Escalation: back/home-style sequence before another run.
                engine.click(46.0 / 460, 960.0 / 1024, False)
                engine.click(0.10, 0.86, False)
                engine.click(0.50, 0.90, False)
                decision_name = 'loop_recovery_escalated'
            else:
                logger.warning(
                    'Detected stuck/cycle state (hard_stuck=%s cycle_stuck=%s), '
                    'saved debug screenshot: %s, attempting recovery tap',
                    hard_stuck,
                    cycle_stuck,
                    debug_path,
                )
                engine.click(0.5, 0.8, False)
                decision_name = 'loop_recovery'

            engine.wait(0.6)
            after = engine.recent_signatures(1)
            after_sig = after[-1] if after else ''
            changed = bool(before_sig and after_sig and before_sig != after_sig)
            if changed:
                self.recovery_success += 1
                self.no_progress_steps = 0

            self._emit_decision(
                i,
                decision_name,
                'clicked' if changed else 'fallback',
                'cycle_guard',
                detail=f'recovery_success={self.recovery_success}/{self.recovery_attempts}',
            )

        if i % 20 == 0:
            logger.info('engine metrics: %s', engine.metrics())

        low_energy_mode = self._contains_low_energy_text(engine)
        if low_energy_mode:
            self._emit_decision(i, 'low_energy', 'fallback', 'energy_mode')
            if self._run_low_energy_fallback(engine, i):
                self._emit_decision(i, 'low_energy', 'clicked', 'free_or_reward')
                return

        # Prioritize skill-choice handling before generic controls to avoid
        # false matches (e.g. "start" matching "starforge").
        if engine.contains('choice', min_confidence=0.9):
            clicked, skill = self._try_click_skill_targets(
                engine,
                self.preferred_skills,
                min_confidence=0.88,
            )
            if clicked:
                self._emit_decision(i, skill, 'clicked', 'skill_preferred_or_alias')
                return

            if engine.click_text('refresh', retry=3, min_confidence=0.85):
                self._emit_decision(i, 'refresh', 'clicked', 'skill_refresh')

            clicked, skill = self._try_click_skill_targets(
                engine,
                self.secondary_skills,
                min_confidence=0.88,
            )
            if clicked:
                self._emit_decision(i, skill, 'clicked', 'skill_secondary_or_alias')
                return

            self._emit_decision(i, 'skill_choice', 'fallback', 'card_force_select')
            fallback_cards = [
                (0.17, 0.44),
                (0.50, 0.44),
                (0.81, 0.44),
            ]
            x, y = fallback_cards[i % len(fallback_cards)]
            engine.click(x, y, wait=False)
            engine.wait(0.6)
            if not engine.contains('choice', min_confidence=0.88):
                return

            engine.click(x, 0.54, wait=False)
            engine.wait(0.6)
            return

        if self._is_in_battle(engine):
            if i % 3 == 0:
                engine.click(0.5, 0.82, False)
                self._emit_decision(i, 'battle_tap', 'clicked', 'battle_heartbeat')
                return
            if i % 9 == 0:
                engine.click(0.92, 0.86, False)
                self._emit_decision(i, 'battle_skill', 'clicked', 'battle_heartbeat')
                return
            self._emit_decision(i, 'battle', 'miss', 'battle_wait_window')
            return

        if low_energy_mode:
            active_controls = list(self.free_controls)
        else:
            active_controls = list(
                self.free_controls + self.home_actions + self.energy_actions
            )

        if i < self.start_cooldown_until and 'start' in active_controls:
            active_controls.remove('start')
            self._emit_decision(i, 'start', 'cooldown', 'start_cooldown_active')

        critical_clicked, critical = self._try_click_critical_controls(engine, i=i)
        if critical_clicked:
            self._emit_decision(i, critical, 'clicked', 'critical_control')
            if critical == 'start':
                self.start_cooldown_until = i + 8
            return

        active_controls = self._safe_targets(active_controls)
        control_clicked, control = self._click_best_text_match(
            engine,
            active_controls,
            min_confidence=0.82,
            exact=False,
        )
        if control_clicked:
            self._emit_decision(i, control, 'clicked', 'nav_label')
            if control == 'start':
                self.start_cooldown_until = i + 8
            return

        if self._contains_blocked_purchase_text(engine):
            self._emit_decision(i, 'purchase_ui', 'blocked', 'high_risk_no_buy')
            engine.click(46.0 / 460, 960.0 / 1024, False)
            engine.click(0.5, 0.1, False)
            return

        if engine.contains('back t', min_confidence=0.9):
            # Keep this lightweight to avoid OCR-heavy retry loops.
            engine.click(380.0 / 460, 280.0 / 1024)
            engine.click(0.5, 0.8, False)
            engine.click(230.0 / 460, 280.0 / 1024)
            engine.click(0.5, 0.8, False)
            engine.click(80.0 / 460, 280.0 / 1024)
            engine.click(0.5, 0.8, False)
            engine.click(46.0 / 460, 960.0 / 1024, False)
            engine.try_click_text('main challenge', min_confidence=0.82)
            self._emit_decision(i, 'backtrack_recover', 'fallback', 'safe_backtrack')
            return

        if engine.contains('revival', min_confidence=0.85):
            if engine.try_click_text(re.compile(r'\bad\b', re.I), min_confidence=0.85):
                self._emit_decision(i, 'ad', 'clicked', 'critical_control')
                return
            engine.click(368.0 / 460, 380.0 / 1024)
            self._emit_decision(i, 'revival', 'fallback', 'critical_text_miss')
            return

        icon_clicked, icon_name = self._try_click_icon_templates(engine)
        if icon_clicked:
            self._emit_decision(i, icon_name, 'clicked', 'icon_template')
            return

        nav_clicked, nav_label = self._try_click_nav_labels(engine)
        if nav_clicked:
            self._emit_decision(i, nav_label, 'clicked', 'nav_label_fuzzy')
            return

        # Home-screen fallback: OCR confidence for "Start" can fluctuate.
        # Honor start cooldown here too, otherwise we can spam the same tap loop.
        if i >= self.start_cooldown_until and engine.contains('start', min_confidence=0.75):
            before = engine.recent_signatures(1)
            before_sig = before[-1] if before else ''
            engine.click(70.0 / 460, 330.0 / 1024, False)
            self.start_cooldown_until = i + 8
            self.last_action = 'start_fallback'
            self._emit_decision(i, 'start', 'fallback', 'start_area_tap')
            self._record_home_click_outcome('start', before_sig, engine, i)
            return

        if i % 7 == 0:
            x, y = self.nav_scan_points[(i // 7) % len(self.nav_scan_points)]
            engine.click(x, y, False)
            self.last_action = 'nav_scan'
            self._emit_decision(i, 'nav_scan', 'fallback', 'scan_point_tap')
            return

        if i % 5 == 0:
            engine.click(0.5, 0.8, False)
            self.last_action = 'center_tap'
            self._emit_decision(i, 'center_tap', 'fallback', 'periodic_recovery')
            return

        self._emit_decision(i, 'none', 'miss', 'no_match')
