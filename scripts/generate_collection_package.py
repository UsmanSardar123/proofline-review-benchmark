import sqlite3
import os
from pathlib import Path
from benchmark.cases.context import ContextManager
from benchmark.cases.registry import CaseRegistry
from benchmark.domain.enums import ContextCondition

con = sqlite3.connect('benchmark.sqlite')
con.row_factory = sqlite3.Row

cm = ContextManager()
reg = CaseRegistry()

out_dir = Path('collection/pending_prompts')
out_dir.mkdir(parents=True, exist_ok=True)

attempts = con.execute('''
    SELECT id, batch_id, case_id, provider_id, context_condition, status
    FROM review_attempts
    WHERE status = 'PENDING'
    ORDER BY case_id, context_condition, provider_id, batch_id
''').fetchall()

index_lines = [
    '# Pending Manual Review Collection Index',
    '',
    f'**Total Pending Attempts:** {len(attempts)}  ',
    '**Generated Date:** 2026-11-22  ',
    '',
    '## Instructions for the Reviewer',
    '1. Open the prompt file linked below for the respective Case, Provider, and Context condition.',
    '2. Copy the entire section under the `---` horizontal rule (the `# Pull Request Review:...` text).',
    '3. **Where to paste:**',
    '   - For `chatgpt-web`: Paste into a fresh session on [chatgpt.com](https://chatgpt.com) (GPT-4o model).',
    '   - For `claude-web`: Paste into a fresh session on [claude.ai](https://claude.ai) (Claude 3.5/3.7 Sonnet model).',
    '4. Copy the complete, unmodified markdown response from the AI reviewer.',
    '5. Save the response into a local file (e.g., `reviews/chatgpt_case01.md`).',
    '6. Ingest the response into the benchmark database using the provided ingestion command.',
    '',
    '## Pending Collection Table',
    '',
    '| # | Case | Provider | Context | Batch ID | Attempt ID | Prompt File | Ingestion Command |',
    '| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |'
]

for idx, att in enumerate(attempts, 1):
    case_id = att['case_id']
    att_id = att['id']
    batch_id = att['batch_id']
    provider_id = att['provider_id']
    context_condition = att['context_condition']

    case_num = int(case_id.replace('case-', ''))
    cond = ContextCondition(context_condition)
    ctx = cm.build_context(case_num, cond)
    prompt = cm.format_review_prompt(ctx)

    provider_slug = 'chatgpt' if 'chatgpt' in provider_id else 'claude'
    cond_slug = 'code_only' if cond == ContextCondition.CODE_ONLY else 'code_and_snapshot'
    filename = f"{case_id}_{cond_slug}_{provider_slug}_{att_id[:8]}.md"
    filepath = out_dir / filename

    content = f"""# BENCHMARK REVIEW PROMPT
- **Case ID:** {case_id}
- **Attempt ID:** {att_id}
- **Batch ID:** {batch_id}
- **Provider Target:** {provider_id}
- **Context Condition:** {context_condition}
- **Base Commit:** {ctx.base_commit}
- **Head Commit:** {ctx.head_commit}

---

{prompt}
"""
    filepath.write_text(content, encoding='utf-8')

    ingest_cmd = f"python -m benchmark ingest --batch-id {batch_id} --case {case_num} --provider {provider_id} --file <response.md>"
    index_lines.append(f"| {idx} | **{case_id}** | `{provider_id}` | `{context_condition}` | `{batch_id}` | `{att_id}` | [{filename}]({filename}) | `{ingest_cmd}` |")

index_path = out_dir / 'README.md'
index_path.write_text('\n'.join(index_lines), encoding='utf-8')
print(f"Successfully generated {len(attempts)} prompt files in {out_dir}")
