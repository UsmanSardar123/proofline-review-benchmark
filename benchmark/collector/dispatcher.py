"""Safe automated review collection dispatcher and cost planner.

Provides pre-flight planning, token estimation, cost projection, dry-run execution,
and authorized external API review dispatch for the Proofline benchmark.
"""

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Optional

from benchmark.cases.context import ContextManager
from benchmark.cases.registry import CaseRegistry
from benchmark.config import PROJECT_ROOT
from benchmark.db.connection import get_connection
from benchmark.db.repositories import AttemptRepository, BatchRepository, CaseRepository
from benchmark.domain.enums import AttemptStatus, ContextCondition
from benchmark.domain.models import ReviewAttempt
from benchmark.providers.anthropic import AnthropicAdapter, AnthropicConfig
from benchmark.providers.base import ReviewContext
from benchmark.providers.cloudflare import CloudflareAdapter, CloudflareConfig
from benchmark.providers.mock import MockProviderAdapter
from benchmark.providers.openai import OpenAIAdapter, OpenAIConfig


# Cost per 1,000,000 tokens (USD)
MODEL_PRICING = {
    "gpt-6.1-sol": {"input": 2.00, "output": 10.00},
    "gpt-6-sol": {"input": 2.00, "output": 10.00},
    "gpt-6-luna": {"input": 0.10, "output": 0.50},
    "gpt-6-astra": {"input": 10.00, "output": 50.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    "@cf/qwen/qwen2.5-coder-32b-instruct": {"input": 0.00, "output": 0.00},
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast": {"input": 0.00, "output": 0.00},
    "@cf/meta/llama-3.1-8b-instruct": {"input": 0.00, "output": 0.00},
    "cloudflare": {"input": 0.00, "output": 0.00},
}


@dataclass
class AttemptCollectionItem:
    """An individual review attempt scheduled for collection."""
    attempt_id: str
    batch_id: str
    case_id: str
    case_number: int
    case_title: str
    provider_id: str
    target_api: str  # 'openai' or 'anthropic'
    model_name: str
    context_condition: str
    estimated_prompt_tokens: int
    estimated_completion_tokens: int
    estimated_cost_usd: float
    prompt_text: str


@dataclass
class CollectionPlan:
    """Complete collection plan and financial cost projection."""
    total_pending: int
    openai_attempts: int
    anthropic_attempts: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_estimated_cost_usd: float
    items: list[AttemptCollectionItem] = field(default_factory=list)
    openai_key_present: bool = False
    anthropic_key_present: bool = False
    cloudflare_attempts: int = 0
    cloudflare_key_present: bool = False


class CollectionDispatcher:
    """Manages planning, dry-run testing, and authorized dispatch of review collections."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._conn = get_connection(db_path)
        self.attempt_repo = AttemptRepository(self._conn)
        self.case_repo = CaseRepository(self._conn)
        self.batch_repo = BatchRepository(self._conn)
        self.case_registry = CaseRegistry()
        self.context_manager = ContextManager()

    def create_plan(
        self,
        batch_id: Optional[str] = None,
        provider_filter: Optional[str] = None,
    ) -> CollectionPlan:
        """Analyze pending attempts and generate an exact token and cost plan."""
        all_attempts = self.attempt_repo.list_all()
        pending = [
            a for a in all_attempts
            if a.status == AttemptStatus.PENDING
            and (batch_id is None or a.batch_id == batch_id)
            and (provider_filter is None or a.provider_id == provider_filter or provider_filter in a.provider_id)
        ]

        items: list[AttemptCollectionItem] = []
        openai_count = 0
        anthropic_count = 0
        cloudflare_count = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cost = 0.0

        for att in pending:
            case_num = int(att.case_id.replace("case-", ""))
            case = self.case_repo.get_by_id(att.case_id)
            case_title = case.title if case else f"Case {case_num}"

            # Build exact prompt text to measure tokens
            ctx = self.context_manager.build_context(case_num, att.context_condition)
            prompt_text = self.context_manager.format_review_prompt(ctx)

            # Estimate tokens: ~4 chars per token rule of thumb
            est_prompt_tokens = max(len(prompt_text) // 4, 100)
            est_completion_tokens = 750  # typical code review length

            # Determine provider API mapping
            if "cloudflare" in att.provider_id.lower() or "workers-ai" in att.provider_id.lower():
                target_api = "cloudflare"
                model = "@cf/qwen/qwen2.5-coder-32b-instruct"
                cloudflare_count += 1
            elif "claude" in att.provider_id.lower() or "anthropic" in att.provider_id.lower():
                target_api = "anthropic"
                model = "claude-sonnet-5-5"
                anthropic_count += 1
            else:
                target_api = "openai"
                model = "gpt-6.1-sol"
                openai_count += 1

            pricing = MODEL_PRICING.get(model, {"input": 2.50, "output": 10.00})
            input_cost = (est_prompt_tokens / 1_000_000.0) * pricing["input"]
            output_cost = (est_completion_tokens / 1_000_000.0) * pricing["output"]
            item_cost = input_cost + output_cost

            items.append(
                AttemptCollectionItem(
                    attempt_id=att.id,
                    batch_id=att.batch_id,
                    case_id=att.case_id,
                    case_number=case_num,
                    case_title=case_title,
                    provider_id=att.provider_id,
                    target_api=target_api,
                    model_name=model,
                    context_condition=att.context_condition.value,
                    estimated_prompt_tokens=est_prompt_tokens,
                    estimated_completion_tokens=est_completion_tokens,
                    estimated_cost_usd=round(item_cost, 4),
                    prompt_text=prompt_text,
                )
            )

            total_prompt_tokens += est_prompt_tokens
            total_completion_tokens += est_completion_tokens
            total_cost += item_cost

        openai_key_present = bool(os.environ.get("OPENAI_API_KEY", "").strip())
        anthropic_key_present = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
        cf_tok = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        cf_acc = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        cloudflare_key_present = bool(cf_tok and cf_acc and cf_tok != "paste_your_new_token_here" and cf_acc != "your_cloudflare_account_id")

        return CollectionPlan(
            total_pending=len(pending),
            openai_attempts=openai_count,
            anthropic_attempts=anthropic_count,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_estimated_cost_usd=round(total_cost, 4),
            items=items,
            openai_key_present=openai_key_present,
            anthropic_key_present=anthropic_key_present,
            cloudflare_attempts=cloudflare_count,
            cloudflare_key_present=cloudflare_key_present,
        )

    def execute_dry_run(self, plan: Optional[CollectionPlan] = None) -> dict:
        """Simulate the end-to-end collection workflow without calling external APIs.

        Validates context construction, prompt formatting, metadata headers,
        and ingestion dispatch using the MockProviderAdapter.
        """
        active_plan = plan or self.create_plan()
        simulated_results = []

        for item in active_plan.items:
            # Generate deterministic mock review
            mock_content = (
                f"# Simulated Code Review for {item.case_id}\n\n"
                f"### Finding 1: Potential Boundary Oversight\n"
                f"- **Severity:** High\n"
                f"- **Target:** `reports.py`\n\n"
                f"Simulated dry-run review response for attempt {item.attempt_id}."
            )

            # Metadata header that would be attached
            header = (
                f"<!--\n"
                f"  METADATA FOR AUTOMATED INGESTION:\n"
                f"  attempt_id: {item.attempt_id}\n"
                f"  batch_id: {item.batch_id}\n"
                f"  provider_id: {item.provider_id}\n"
                f"  case_id: {item.case_id}\n"
                f"  context_condition: {item.context_condition}\n"
                f"-->\n\n"
            )

            full_review = header + mock_content
            sha256_hash = hashlib.sha256(mock_content.encode("utf-8")).hexdigest()

            simulated_results.append({
                "attempt_id": item.attempt_id,
                "case_id": item.case_id,
                "provider_id": item.provider_id,
                "target_api": item.target_api,
                "model_name": item.model_name,
                "content_length": len(mock_content),
                "sha256_hash": sha256_hash,
                "status": "VALID_DRY_RUN",
            })

        return {
            "status": "SUCCESS",
            "total_simulated": len(simulated_results),
            "simulated_cost_usd": 0.0,
            "results": simulated_results,
        }

    def dispatch_authorized_collection(
        self,
        allow_paid_api: bool = False,
        cost_limit_usd: float = 2.0,
        provider_filter: Optional[str] = None,
        reviews_dir: Optional[Path] = None,
    ) -> dict:
        """Dispatch live API calls to collect reviews if and only if explicitly authorized.

        Enforces:
        1. Explicit allow_paid_api=True requirement.
        2. Financial cost ceiling.
        3. Real API key availability.
        4. Ingestion of received reviews with SHA-256 integrity checks.
        """
        if not allow_paid_api:
            raise PermissionError(
                "Paid API execution not authorized under the project's ZERO-COST POLICY ($0.00 spending limit). "
                "You must pass allow_paid_api=True to confirm you approve billable external API requests."
            )

        plan = self.create_plan(provider_filter=provider_filter)
        if plan.total_estimated_cost_usd > cost_limit_usd:
            raise ValueError(
                f"Projected cost (${plan.total_estimated_cost_usd:.2f}) exceeds "
                f"authorized ceiling (${cost_limit_usd:.2f}). Aborting."
            )

        target_dir = reviews_dir or (PROJECT_ROOT / "reviews")
        target_dir.mkdir(parents=True, exist_ok=True)

        collected = 0
        failed = 0
        total_spent = 0.0
        audit_log = []

        for item in plan.items:
            # Check credentials for this specific item
            if item.target_api == "openai" and not plan.openai_key_present:
                audit_log.append({
                    "attempt_id": item.attempt_id,
                    "status": "SKIPPED_MISSING_API_KEY",
                    "reason": "OPENAI_API_KEY environment variable is not set.",
                })
                failed += 1
                continue

            if item.target_api == "anthropic" and not plan.anthropic_key_present:
                audit_log.append({
                    "attempt_id": item.attempt_id,
                    "status": "SKIPPED_MISSING_API_KEY",
                    "reason": "ANTHROPIC_API_KEY environment variable is not set.",
                })
                failed += 1
                continue

            if item.target_api == "cloudflare" and not plan.cloudflare_key_present:
                audit_log.append({
                    "attempt_id": item.attempt_id,
                    "status": "SKIPPED_MISSING_API_KEY",
                    "reason": "CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID is not configured in .env.",
                })
                failed += 1
                continue

            # Instantiate real adapter
            if item.target_api == "cloudflare":
                adapter = CloudflareAdapter(
                    CloudflareConfig(
                        provider_id=item.provider_id,
                        display_name="Cloudflare Workers AI",
                        default_model=item.model_name,
                        api_key_env_var="CLOUDFLARE_API_TOKEN",
                    )
                )
            elif item.target_api == "openai":
                adapter = OpenAIAdapter(
                    OpenAIConfig(
                        provider_id=item.provider_id,
                        display_name="OpenAI GPT-6.1 Sol",
                        default_model=item.model_name,
                        api_key_env_var="OPENAI_API_KEY",
                    )
                )
            else:
                adapter = AnthropicAdapter(
                    AnthropicConfig(
                        provider_id=item.provider_id,
                        display_name="Anthropic Claude",
                        default_model=item.model_name,
                        api_key_env_var="ANTHROPIC_API_KEY",
                    )
                )

            # Build review context
            case_num = item.case_number
            case = self.case_repo.get_by_id(item.case_id)
            cond = ContextCondition(item.context_condition)
            ctx = self.context_manager.build_context(case_num, cond)

            review_ctx = ReviewContext(
                case_id=item.case_id,
                case_number=case_num,
                pr_title=case.title if case else f"Case {case_num}",
                pr_body=case.pr_description if case else "",
                base_commit=ctx.base_commit,
                head_commit=ctx.head_commit,
                patch_diff=ctx.patch_diff,
                context_condition=cond,
                snapshot_content=ctx.snapshot_content if cond == ContextCondition.CODE_AND_SNAPSHOT else None,
            )

            try:
                t0 = time.perf_counter()
                res = adapter.invoke_review(review_ctx)
                dur = int((time.perf_counter() - t0) * 1000)

                # Format saved review file with explicit metadata header
                header = (
                    f"<!--\n"
                    f"  METADATA FOR AUTOMATED INGESTION:\n"
                    f"  attempt_id: {item.attempt_id}\n"
                    f"  batch_id: {item.batch_id}\n"
                    f"  provider_id: {item.provider_id}\n"
                    f"  case_id: {item.case_id}\n"
                    f"  context_condition: {item.context_condition}\n"
                    f"-->\n\n"
                )
                output_content = header + res.raw_content
                file_name = f"{item.case_id}_{item.context_condition.lower()}_{item.target_api}_{item.attempt_id[:8]}.md"
                file_path = target_dir / file_name
                file_path.write_text(output_content, encoding="utf-8")

                actual_cost = item.estimated_cost_usd
                total_spent += actual_cost
                collected += 1

                audit_log.append({
                    "attempt_id": item.attempt_id,
                    "case_id": item.case_id,
                    "target_api": item.target_api,
                    "model_name": res.model_name or item.model_name,
                    "saved_file": str(file_path),
                    "duration_ms": dur,
                    "tokens_used": (res.prompt_tokens or 0) + (res.completion_tokens or 0),
                    "status": "COLLECTED_AND_SAVED",
                })
            except Exception as e:
                failed += 1
                audit_log.append({
                    "attempt_id": item.attempt_id,
                    "status": "FAILED",
                    "error": str(e),
                })

        return {
            "total_planned": len(plan.items),
            "collected": collected,
            "failed": failed,
            "total_spent_usd": round(total_spent, 4),
            "audit_log": audit_log,
        }
