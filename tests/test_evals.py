from payguard.evals import run


def test_quality_gate_passes():
    rep = run()
    assert rep["gate_passed"], rep
