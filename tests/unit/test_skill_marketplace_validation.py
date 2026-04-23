from core.skill_marketplace import SkillMarketplace, SkillRecord


def test_skill_validation_required_for_promote(tmp_path):
    market = SkillMarketplace(tmp_path / "skills.json")
    market.register(
        SkillRecord(
            skill_id="s1",
            version="1.0.0",
            risk_level="low",
            cost_class="standard",
            compatible_with=">=3.2.0",
        )
    )
    market.approve("s1", "1.0.0")
    market.validate("s1", "1.0.0", sandbox_passed=False, contract_passed=False, security_passed=False)
    assert market.promote("s1", "1.0.0") is False

    market.validate("s1", "1.0.0", sandbox_passed=True, contract_passed=True, security_passed=True)
    assert market.promote("s1", "1.0.0") is True
