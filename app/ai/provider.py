"""AI provider interface: isolates AI integration behind a clean interface."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Abstract interface for AI providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available."""
        pass

    @abstractmethod
    def generate_commentary(self, structured_data: dict, vertical: str) -> str:
        """Generate management commentary from structured analytical results."""
        pass


class LocalAIProvider(AIProvider):
    """Deterministic template-based provider. Always available, no API key needed."""

    def is_available(self) -> bool:
        return True

    def generate_commentary(self, structured_data: dict, vertical: str) -> str:
        """Generate deterministic commentary from structured results."""
        lines = []
        kpis = structured_data.get("kpis", {})
        findings = structured_data.get("findings", [])
        profitability = structured_data.get("profitability", {})

        if kpis.get("total_revenue"):
            lines.append(
                f"The business generated {kpis['total_revenue']:,.2f} in total revenue "
                f"across {kpis.get('transaction_count', 'N/A')} transactions."
            )

        if kpis.get("unique_customers"):
            lines.append(
                f"Revenue was generated across {kpis['unique_customers']} unique customers "
                f"and {kpis.get('unique_products', 'N/A')} products."
            )

        if profitability.get("gross_margin_pct") is not None:
            margin = profitability["gross_margin_pct"]
            if margin < 10:
                lines.append(
                    f"The gross margin of {margin:.1f}% is low, "
                    "indicating potential pricing or cost management issues."
                )
            elif margin > 30:
                lines.append(
                    f"The gross margin of {margin:.1f}% is strong, suggesting effective pricing strategy."
                )
            else:
                lines.append(
                    f"The gross margin of {margin:.1f}% is within a moderate range."
                )

        critical_findings = [f for f in findings if f.get("severity") in ("critical", "high")]
        if critical_findings:
            lines.append(
                f"The analysis identified {len(critical_findings)} high-priority finding(s) "
                "that require management attention."
            )
            for f in critical_findings[:3]:
                lines.append(f"  - {f.get('title', 'Unknown issue')}: {f.get('explanation', '')}")

        if not lines:
            lines.append("Insufficient data for detailed commentary. Please review the findings section for specific insights.")

        return "\n".join(lines)


class CloudAIProvider(AIProvider):
    """Cloud-based AI provider using an external API. Requires API key in environment."""

    def __init__(self, provider_name: str = "openai"):
        self.provider_name = provider_name
        self.api_key = os.environ.get(f"{provider_name.upper()}_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_commentary(self, structured_data: dict, vertical: str) -> str:
        """Generate commentary using an external AI API."""
        if not self.is_available():
            # Fall back to local provider
            return LocalAIProvider().generate_commentary(structured_data, vertical)

        # This is a placeholder for actual API integration.
        # In production, this would call the actual AI API (OpenAI, Anthropic, etc.)
        # The key principle: only send structured analytical results, never raw data.
        # The AI must only make claims supported by the supplied metrics.
        try:
            # Attempt to use the API if available
            # For now, fall back to local provider
            return LocalAIProvider().generate_commentary(structured_data, vertical)
        except Exception:
            return LocalAIProvider().generate_commentary(structured_data, vertical)


def get_ai_provider(use_ai: bool = False) -> AIProvider:
    """Get the appropriate AI provider based on configuration."""
    if use_ai:
        cloud = CloudAIProvider()
        if cloud.is_available():
            return cloud
    return LocalAIProvider()
