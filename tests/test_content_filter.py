"""Tests for FOSTA/SESTA content filter — critical for legal compliance."""
import pytest
from app.services.content_filter import scan_text


class TestFlaggedContent:
    """These MUST be flagged — failure means legal risk."""

    def test_escort_terminology(self):
        assert scan_text("I offer escort service in Miami")[0] is True
        assert scan_text("Looking for full service GFE")[0] is True
        assert scan_text("incall or outcall available")[0] is True

    def test_escort_abbreviations(self):
        assert scan_text("GFE experience guaranteed")[0] is True
        assert scan_text("BBBJ included")[0] is True
        assert scan_text("PSE available")[0] is True
        assert scan_text("MSOG okay")[0] is True

    def test_explicit_solicitation(self):
        assert scan_text("pay for sex tonight")[0] is True
        assert scan_text("sex for money only")[0] is True
        assert scan_text("selling sex")[0] is True
        assert scan_text("commercial sex")[0] is True

    def test_prostitution_terms(self):
        assert scan_text("I'm not a hooker but")[0] is True
        assert scan_text("call girl services")[0] is True
        assert scan_text("prostitution is legal here")[0] is True

    def test_trafficking_indicators(self):
        assert scan_text("she's underage but mature")[0] is True
        assert scan_text("barely legal teens")[0] is True
        assert scan_text("my girls work for me")[0] is True
        assert scan_text("fresh meat available")[0] is True
        assert scan_text("I control everything")[0] is True

    def test_payment_slang(self):
        assert scan_text("200 roses per hour")[0] is True
        assert scan_text("donation required upfront")[0] is True
        assert scan_text("hourly rate is 300")[0] is True

    def test_returns_matched_term(self):
        flagged, term = scan_text("I offer escort service")
        assert flagged is True
        assert term == "escort service"


class TestAllowedContent:
    """These MUST NOT be flagged — false positives block real users."""

    def test_normal_sugar_language(self):
        assert scan_text("Looking for a generous sugar daddy")[0] is False
        assert scan_text("I want a monthly allowance")[0] is False
        assert scan_text("Seeking an arrangement with clear expectations")[0] is False

    def test_lifestyle_descriptions(self):
        assert scan_text("I love fine dining and travel")[0] is False
        assert scan_text("Let's meet at a nice restaurant")[0] is False
        assert scan_text("I'm looking for mentorship and companionship")[0] is False

    def test_financial_terms(self):
        assert scan_text("My income is over 500K")[0] is False
        assert scan_text("I can provide financial support")[0] is False
        assert scan_text("PPM or monthly, open to either")[0] is False

    def test_relationship_terms(self):
        assert scan_text("Long-term arrangement preferred")[0] is False
        assert scan_text("No strings attached")[0] is False
        assert scan_text("Friends with benefits")[0] is False
        assert scan_text("Sugar relationship")[0] is False

    def test_kink_lifestyle_terms(self):
        assert scan_text("I'm kink-friendly and open-minded")[0] is False
        assert scan_text("Dominant personality, take charge type")[0] is False
        assert scan_text("ENM, ethical non-monogamy")[0] is False
        assert scan_text("Open relationship, polyamorous")[0] is False

    def test_empty_and_none(self):
        assert scan_text("")[0] is False
        assert scan_text(None)[0] is False

    def test_normal_bios(self):
        assert scan_text("CEO by day, foodie by night. I've eaten at 47 Michelin-starred restaurants.")[0] is False
        assert scan_text("Nursing student. I study 60 hours a week and still look this good.")[0] is False
        assert scan_text("Semi-retired at 52. Spend half my time in New York, half in Miami.")[0] is False


class TestEdgeCases:
    def test_case_insensitive(self):
        assert scan_text("ESCORT SERVICE")[0] is True
        assert scan_text("Escort Service")[0] is True
        assert scan_text("eScOrT sErViCe")[0] is True

    def test_term_must_be_whole_word(self):
        # "escort" alone shouldn't match "escort service" pattern
        # but "escorted" shouldn't match "escort service" either
        flagged, _ = scan_text("I escorted her to the party")
        # This depends on whether "escort" alone is in the list
        # Currently only "escort service" and "escort agency" are flagged
        assert flagged is False

    def test_long_text_with_hidden_term(self):
        text = "A" * 1000 + " escort service " + "B" * 1000
        assert scan_text(text)[0] is True

    def test_multiline_text(self):
        text = "Normal bio here.\nI love travel.\nescort service available.\nMore text."
        assert scan_text(text)[0] is True
