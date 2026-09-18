from app.agents.case_analysis import CaseAnalysisAgent
from app.agents.policy_evidence_agent import PolicyEvidenceAgent
from app.agents.coverage_agent import CoverageExclusionAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.validation_agent import ValidationAgent


class ClaimWorkflow:
    def __init__(self):
        self.case_analysis_agent = CaseAnalysisAgent()
        self.policy_evidence_agent = PolicyEvidenceAgent()
        self.coverage_agent = CoverageExclusionAgent()
        self.decision_agent = DecisionAgent()
        self.validation_agent = ValidationAgent()

    def run(self, claim: dict) -> dict:
        state = {
            "case_id": claim["case_id"],
            "claim": claim,
            "trace": [],
        }

        state = self.case_analysis_agent.run(state)
        state = self.policy_evidence_agent.run(state)
        state = self.coverage_agent.run(state)
        state = self.decision_agent.run(state)
        state = self.validation_agent.run(state)

        return state