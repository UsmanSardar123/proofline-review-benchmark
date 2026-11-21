# AWS Deployment & Verification Audit

**Stack Name:** `ai-review-bench`  
**Application Tag:** `Application=ai-review-benchmarks`  
**Local Packaging & Smoke Test:** **VERIFIED & COMPLETED** (receipt `receipt_at: 101`, commit `79b3839`)  
**Live Cloud Deployment Status:** **NOT PERFORMED** (Candidate skipped due to absence of AWS account / credentials)  
**Cloud Lambda Invocation:** **NOT PERFORMED**  
**CloudWatch Live Verification:** **NOT PERFORMED**  
**Cloud Teardown:** **NOT PERFORMED**  

---

## 1. Local Smoke Check (Offline Verification)

Before touching AWS, the CloudFormation package and inline Lambda handler can be verified locally on any machine with Python 3.10+ and SQLite:

```powershell
$py = "C:\Users\hp\AppData\Local\Programs\Python\Python314\python.exe"

# Package inline CloudFormation template
& $py aws/deploy.py package --output aws_package_test.json

# Run local in-memory SQLite smoke check
& $py aws/deploy.py smoke --template aws_package_test.json

# Cleanup local test template
Remove-Item aws_package_test.json
```

**Expected Local Receipt Output:**
```json
{
  "commit": "79b3839abbfef580547f336b619008069b81254a",
  "request_id": "local-smoke",
  "report": "Weekly orders",
  "delivered_this_run": 1,
  "receipt_at": 101,
  "summary": {
    "delivered": 1,
    "pending": 0
  }
}
```

*Note:* The request ID `local-smoke` proves local execution. Real AWS execution returns an authentic AWS UUID request ID (e.g. `c7a4b11e-89bf-481b-a9b0-9b48c68832a1`).

---

## 2. Option A: Cloud Deployment via Local AWS CLI

### Prerequisites:
1. Install AWS CLI v2.
2. Configure credentials with CloudFormation and Lambda permissions:
   ```bash
   aws configure
   ```
3. Verify caller identity:
   ```bash
   aws sts get-caller-identity
   ```

### Execution Steps:
```bash
export AWS_REGION="us-east-1"
export AWS_LAMBDA_ROLE_ARN="arn:aws:iam::<ACCOUNT_ID>:role/ai-review-bench-runtime"

# 1. Deploy Stack
python aws/deploy.py deploy --region "$AWS_REGION" --stack ai-review-bench --role-arn "$AWS_LAMBDA_ROLE_ARN"

# 2. Verify Invocation & Capture Receipt
python aws/deploy.py verify --region "$AWS_REGION" --stack ai-review-bench > evidence/aws/verification-receipt.json

# 3. Clean Up (Teardown Stack Immediately)
python aws/deploy.py delete --region "$AWS_REGION" --stack ai-review-bench
```

---

## 3. Option B: Cloud Deployment via GitHub Actions (Recommended)

The repository includes a ready-to-run GitHub Actions workflow ([.github/workflows/aws.yml](file:///c:/Users/hp/Desktop/proofline-review-benchmark/.github/workflows/aws.yml)).

### Steps:
1. Deploy `aws/github-roles.yaml` CloudFormation stack in AWS to create the GitHub OIDC trust role.
2. Add three Repository Variables in GitHub (**Settings → Secrets and variables → Actions → Variables**):
   - `AWS_REGION` (e.g. `us-east-1`)
   - `AWS_DEPLOY_ROLE_ARN` (the deployer role ARN from stack output)
   - `AWS_LAMBDA_ROLE_ARN` (the runtime role ARN from stack output)
3. Navigate to **Actions → AWS sample deployment → Run workflow**:
   - Branch: `main`
   - Operation: `deploy`
4. The workflow will package the commit, assume the role via OIDC, deploy the stack, invoke the Lambda, verify the receipt, and log the real AWS request ID.
5. Once verified, run workflow with Operation: `delete` to tear down the stack.
