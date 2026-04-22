"""AgentCard — A2A discovery metadata for each agent.

Compatible with the Google A2A protocol agent-card format.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AgentSkill:
    name: str
    description: str


@dataclass
class AgentCard:
    """Describes the agent for discovery via A2A protocol."""

    name: str
    version: str
    description: str
    endpoint: str
    framework: str = "MAF"
    skills: List[AgentSkill] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "endpoint": self.endpoint,
            "framework": self.framework,
            "skills": [{"name": s.name, "description": s.description} for s in self.skills],
            "metadata": self.metadata,
        }


def build_agent_card(agent_cfg: dict) -> AgentCard:
    """Build an AgentCard from an agents_config.json agent entry."""
    host = os.getenv("A2A_SERVER_HOST", "localhost")
    port = os.getenv("A2A_SERVER_PORT", os.getenv("PORT", "8503"))
    name = agent_cfg["name"]
    prefix = agent_cfg.get("route_prefix", name)
    endpoint = f"http://{host}:{port}/a2a/{prefix}"

    skills = [
        AgentSkill(name=s["name"], description=s["description"])
        for s in agent_cfg.get("skills", [])
    ]
    # Auto-create a skill from the agent description if none configured
    if not skills:
        skills = [AgentSkill(name=name, description=agent_cfg.get("description", ""))]

    tool_mode = agent_cfg.get("tool_mode", "none")
    mcp_tools = agent_cfg.get("mcp_tools", [])

    return AgentCard(
        name=name,
        version=agent_cfg.get("version", "1.0.0"),
        description=agent_cfg.get("description", ""),
        endpoint=endpoint,
        skills=skills,
        metadata={
            "protocol": "A2A",
            "output_modes": ["text"],
            "streaming": True,
            "tool_mode": tool_mode,
            "mcp_tools": mcp_tools,
        },
    )
