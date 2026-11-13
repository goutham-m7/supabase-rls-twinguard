from twinguard.controls import safe_repair
from twinguard.runner import run_attempt
from twinguard.scenario import scenarios


def test_insert_policy_opening_only_second_tenant_is_caught(cluster):
    task = scenarios()[0]
    def second_tenant_only(s):
        return safe_repair(s) + f"CREATE POLICY slipped_insert ON public.invoices_00 FOR INSERT TO authenticated WITH CHECK (tenant_id='{s.tenants[1]}');"
    result = run_attempt(cluster, task, second_tenant_only, "second-tenant-insert", 1)
    assert not result["passed"]
    assert result["unauthorized_writes"] > 0
