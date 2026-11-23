# 08 — AWS Readiness Assessment

*Assessed by inspecting `aws/deploy.py`, `aws/handler.py`, `aws/stack.json`, `aws/github-roles.yaml`, `.github/workflows/check.yml`, `.github/workflows/aws.yml`, and `docs/aws-live-verification.md`, and running local `package` + `smoke` commands without creating any AWS resources.*

---

## 1. What Runs on AWS & Why

**Important Clarification:** The **benchmark evaluation engine** (`benchmark/`) does **not** run on AWS. Instead, the **target sample application** (`reports.py` + `migrations/001_initial.sql`) is packaged and deployed to AWS Lambda as a realistic serverless workload fixture to verify end-to-end systems, CloudFormation, IAM OIDC, and CI/CD skills.

---

## 2. AWS Services & Files Inspected

| Component | File | Purpose |
| :--- | :--- | :--- |
| **CloudFormation Template** | `aws/stack.json` | Creates 2 resources: `ReportLogs` (`AWS::Logs::LogGroup`, `/aws/lambda/${AWS::StackName}`, 1-day retention) and `ReportFunction` (`AWS::Lambda::Function`, `python3.12`, 128 MB RAM, 10s timeout, inline `ZipFile` code). **No API Gateway, DynamoDB, or S3 is used.** |
| **Lambda Handler** | `aws/handler.py` | `handler(event, context)` opens an **in-memory SQLite** DB (`:memory:`), runs `reports.migrate(db)`, schedules a report, calls `reports.deliver_due()`, queries `receipts`, and returns a JSON receipt with `SOURCE_COMMIT` and `context.aws_request_id`. |
| **Packaging & Deploy CLI** | `aws/deploy.py` | Supports 5 operations: `package`, `smoke`, `deploy`, `verify`, `delete`. Packages `reports.py`, `migrations/*`, and `aws/handler.py` inline into `aws/stack.json` (must stay under CloudFormation's 51,200-byte inline template limit). |
| **IAM & GitHub OIDC** | `aws/github-roles.yaml` | Creates `RuntimeRole` (Lambda execution + CloudWatch Logs write) and `DeploymentRole` (GitHub OIDC `sts:AssumeRoleWithWebIdentity` scoped to `repo:<owner>/<repo>:ref:refs/heads/main`, with CloudFormation, Lambda, `iam:PassRole`, and Logs permissions). |
| **GitHub Actions** | `.github/workflows/check.yml` | Runs on PR/push to `main`: executes `aws/deploy.py package` + `smoke` and `unittest discover tests`. |
| **GitHub Actions (AWS)** | `.github/workflows/aws.yml` | Manual `workflow_dispatch` on `main` (`deploy` or `delete`): packages, assumes `AWS_DEPLOY_ROLE_ARN` via OIDC, runs `deploy` + `verify` (via `aws lambda invoke`), or `delete`. |

---

## 3. Required GitHub Variables & IAM Setup (Manual)

To run `.github/workflows/aws.yml`, you must have an AWS account and configure:
1. Deploy `aws/github-roles.yaml` in AWS with `GitHubSubject = repo:UsmanSardar123/proofline-review-benchmark:ref:refs/heads/main` (and ensure the GitHub OIDC provider `token.actions.githubusercontent.com` exists in IAM).
2. Add 3 GitHub Repository Variables:
   - `AWS_REGION` (e.g., `us-east-1`)
   - `AWS_DEPLOY_ROLE_ARN` (output `DeploymentRoleArn`)
   - `AWS_LAMBDA_ROLE_ARN` (output `RuntimeRoleArn`)
3. Merge `feature/benchmark-engine` into `main` (since `aws.yml` enforces `if: github.ref == 'refs/heads/main'`), or run `aws/deploy.py deploy` + `verify` + `delete` locally with AWS CLI v2.

---

## 4. Verification Status Matrix

| Stage | Status | Evidence |
| :--- | :---: | :--- |
| **Locally tested (`smoke`)** | **VERIFIED** | Ran `aws/deploy.py package` + `smoke` on 2026-11-22: returned `commit: 9d3773291b175b5a49fbb1ef3259f08968c573e8`, `request_id: "local-smoke"`, `delivered_this_run: 1`, `receipt_at: 101`, `summary: {"delivered": 1, "pending": 0}`. |
| **Package validated** | **VERIFIED** | `aws/deploy.py package` produced a valid JSON CloudFormation template under the 51,200-byte inline limit. |
| **Infrastructure template validated** | **PARTIAL** | Valid JSON locally, **not** validated against `aws cloudformation validate-template`. |
| **Deployed to AWS** | **NOT PERFORMED** | No AWS account/credentials configured (`docs/aws-live-verification.md`). |
| **Successfully invoked in AWS** | **NOT PERFORMED** | No live `aws lambda invoke` receipt exists. |
| **Verified through CloudWatch** | **NOT PERFORMED** | No CloudWatch log stream verified. |
