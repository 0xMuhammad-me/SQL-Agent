from __future__ import annotations

from app import build_sql_agent
from orchestration import AgentRequest


def main() -> None:
    agent = build_sql_agent()
    question: str = input("Question: ").strip()
    result = agent.run(AgentRequest(question=question))
    if result.answer:
        print(result.answer)
    elif result.clarification_question:
        print(result.clarification_question)
    else:
        print(result.status.value)
        for issue in result.issues:
            print(f"- {issue}")


if __name__ == "__main__":
    main()
