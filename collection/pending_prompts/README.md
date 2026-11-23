# Pending Manual Review Collection Index

**Total Pending Attempts:** 19  
**Last Synchronized:** 2026-11-22 13:46:52 UTC  

## Instructions for the Reviewer
1. Open the prompt file linked below for the respective Case, Provider, and Context condition.
2. Copy the entire section under the `---` horizontal rule (the `# Pull Request Review:...` text).
3. **Where to paste:**
   - For `chatgpt-web`: Paste into a fresh session on [chatgpt.com](https://chatgpt.com) (GPT-4o).
   - For `claude-web`: Paste into a fresh session on [claude.ai](https://claude.ai) (Claude 3.5/3.7 Sonnet).
4. Copy the complete, unmodified markdown response from the AI reviewer.
5. Save the response into a local file in `reviews/` (e.g. `reviews/case-03_claude_response.md`).
   Include metadata header block or name it using `<case>_<context>_<provider>_response.md`.
6. Run `python -m benchmark automate` to automatically match, ingest, score, and regenerate reports.

## Pending Collection Table

| # | Case | Provider | Context | Batch ID | Attempt ID | Prompt File |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **case-02** | `claude-web` | `CODE_ONLY` | `batch-7b358964` | `att-2629b40a9666` | [case-02_code_only_claude_att-2629.md](case-02_code_only_claude_att-2629.md) |
| 2 | **case-03** | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-2c30ac581db0` | [case-03_code_only_chatgpt_att-2c30.md](case-03_code_only_chatgpt_att-2c30.md) |
| 3 | **case-03** | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-3988adbbc39f` | [case-03_code_only_claude_att-3988.md](case-03_code_only_claude_att-3988.md) |
| 4 | **case-04** | `chatgpt-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-466d4194ecef` | [case-04_code_and_snapshot_chatgpt_att-466d.md](case-04_code_and_snapshot_chatgpt_att-466d.md) |
| 5 | **case-04** | `claude-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-5028cc3f12e0` | [case-04_code_and_snapshot_claude_att-5028.md](case-04_code_and_snapshot_claude_att-5028.md) |
| 6 | **case-04** | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-b1377bcb7bc8` | [case-04_code_only_chatgpt_att-b137.md](case-04_code_only_chatgpt_att-b137.md) |
| 7 | **case-04** | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-969af64be053` | [case-04_code_only_claude_att-969a.md](case-04_code_only_claude_att-969a.md) |
| 8 | **case-05** | `chatgpt-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-836b91f3b28c` | [case-05_code_and_snapshot_chatgpt_att-836b.md](case-05_code_and_snapshot_chatgpt_att-836b.md) |
| 9 | **case-05** | `claude-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-e36d85f2240b` | [case-05_code_and_snapshot_claude_att-e36d.md](case-05_code_and_snapshot_claude_att-e36d.md) |
| 10 | **case-05** | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-8c2e145b504b` | [case-05_code_only_chatgpt_att-8c2e.md](case-05_code_only_chatgpt_att-8c2e.md) |
| 11 | **case-05** | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-d0cdd8768c72` | [case-05_code_only_claude_att-d0cd.md](case-05_code_only_claude_att-d0cd.md) |
| 12 | **case-06** | `chatgpt-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-f620d60e5076` | [case-06_code_and_snapshot_chatgpt_att-f620.md](case-06_code_and_snapshot_chatgpt_att-f620.md) |
| 13 | **case-06** | `claude-web` | `CODE_AND_SNAPSHOT` | `batch-8aca4c4d` | `att-f965cdbb31df` | [case-06_code_and_snapshot_claude_att-f965.md](case-06_code_and_snapshot_claude_att-f965.md) |
| 14 | **case-06** | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-2a56a9c459ca` | [case-06_code_only_chatgpt_att-2a56.md](case-06_code_only_chatgpt_att-2a56.md) |
| 15 | **case-06** | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-470ea9a28633` | [case-06_code_only_claude_att-470e.md](case-06_code_only_claude_att-470e.md) |
| 16 | **case-07** | `chatgpt-web` | `CODE_ONLY` | `batch-7b358964` | `att-cbe5400d576f` | [case-07_code_only_chatgpt_att-cbe5.md](case-07_code_only_chatgpt_att-cbe5.md) |
| 17 | **case-07** | `claude-web` | `CODE_ONLY` | `batch-7b358964` | `att-5bb0d7133dee` | [case-07_code_only_claude_att-5bb0.md](case-07_code_only_claude_att-5bb0.md) |
| 18 | **case-08** | `chatgpt-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-8a22c53c514b` | [case-08_code_only_chatgpt_att-8a22.md](case-08_code_only_chatgpt_att-8a22.md) |
| 19 | **case-08** | `claude-web` | `CODE_ONLY` | `batch-8e1fac6e` | `att-5a753f436114` | [case-08_code_only_claude_att-5a75.md](case-08_code_only_claude_att-5a75.md) |