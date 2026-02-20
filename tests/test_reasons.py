from game_driver.reasons import SequentialClickReason, SurvivorDecisionReason


def test_sequential_click_reason_values_are_stable_strings():
    assert SequentialClickReason.STATE_CHANGED == 'state_changed'
    assert SequentialClickReason.NO_STATE_CHANGE == 'no_state_change'
    assert SequentialClickReason.NO_MATCH == 'no_match'


def test_survivor_reason_values_are_stable_strings():
    assert SurvivorDecisionReason.BOOT == 'boot'
    assert SurvivorDecisionReason.CYCLE_GUARD == 'cycle_guard'
    assert SurvivorDecisionReason.NO_MATCH == 'no_match'
