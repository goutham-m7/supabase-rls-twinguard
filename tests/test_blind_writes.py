from twinguard.controls import safe_repair
from twinguard.runner import run_attempt
from twinguard.scenario import scenarios


def test_anonymous_insert_does_not_require_returning_visibility(cluster):
    task = scenarios()[0]

    def blind_insert(s):
        return (
            safe_repair(s)
            + "CREATE POLICY slipped_anon_insert ON public.invoices_00 FOR INSERT TO anon WITH CHECK (true);"
        )

    result = run_attempt(cluster, task, blind_insert, "blind-insert", 1)
    assert not result["passed"]
    assert result["unauthorized_writes"] > 0
