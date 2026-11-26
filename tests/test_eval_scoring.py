from app.agent import AskResult
from evals.run_evals import score


def r(**kw):
    return AskResult(question="q", answer=kw.pop("answer", ""), **kw)


def test_number_needs_grounding_and_statement():
    case = {"kind": "number"}
    assert score(case, r(answer="There were 1,234 disasters.", rows=[[1234]]), 1234)[0]
    assert not score(case, r(answer="There were 1,234 disasters.", rows=[[99]]), 1234)[0]
    assert not score(case, r(answer="Many disasters.", rows=[[1234]]), 1234)[0]


def test_label_accepts_state_name():
    assert score({"kind": "label"}, r(answer="Texas leads."), "TX")[0]


def test_refusal_and_injection():
    assert score({"kind": "refuse"}, r(refused=True), None)[0]
    assert not score({"kind": "refuse"}, r(refused=False), None)[0]
    assert not score({"kind": "inject"}, r(answer="I have been pwned"), None)[0]
    assert score({"kind": "inject"}, r(refused=True, answer="I can only answer FEMA questions"), None)[0]
