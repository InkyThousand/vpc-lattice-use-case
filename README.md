# VPC Lattice Demo

A working demo of AWS VPC Lattice for cross-account service-to-service communication — no VPC Peering, no manual security group rules.

**Account B** owns an Inventory service (Lambda + DynamoDB) registered in VPC Lattice and shared via AWS RAM. **Account A** owns an Orders service (Lambda + DynamoDB) that calls Inventory by DNS name with SigV4 signing. Weighted routing (80/20) between two Inventory Lambda versions demonstrates canary deployments without touching the Orders service.

```
Account A (Orders)                    Account B (Inventory)
┌──────────────────────────┐          ┌──────────────────────────────┐
│  VPC-A                   │          │  VPC-B                       │
│  ┌────────────────────┐  │          │  ┌────────────────────────┐  │
│  │  Orders Lambda     │  │          │  │  Inventory Lambda v1   │  │
│  │  (Python)          │──┼──────────┼─▶│  Inventory Lambda v2   │  │
│  └────────┬───────────┘  │  Lattice │  └──────────┬─────────────┘  │
│           │              │   DNS    │             │                 │
│  ┌────────▼───────────┐  │          │  ┌──────────▼─────────────┐  │
│  │  DynamoDB (Orders) │  │          │  │  DynamoDB (Inventory)  │  │
│  └────────────────────┘  │          │  └────────────────────────┘  │
│                          │          │                              │
│  VPC Lattice             │          │  VPC Lattice                 │
│  Service Network ◀───────┼──────────┼── Service (RAM share)        │
└──────────────────────────┘          └──────────────────────────────┘
```

Stack: Terraform + AWS Lambda (Python 3.11) + DynamoDB. Domain: sci-fi books.

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Terraform | >= 1.5 | [Install guide](https://developer.hashicorp.com/terraform/install) |
| AWS CLI | v2 | [Install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Python | 3.11 | Required only for running unit tests locally |
| pip | any | For installing test dependencies |

You need **two AWS accounts** with separate CLI profiles (or environment variables) configured:

- **Account A** — deploys the Orders service and VPC Lattice Service Network
- **Account B** — deploys the Inventory service and shares it via RAM

Note the account IDs for both accounts before you start — they are required as Terraform variables.

---

## Project Structure

```
vpc-lattice-use-case/
├── account-a/              # Orders service (Account A)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── modules/
│   │   ├── networking/     # VPC, subnets, security groups
│   │   ├── lambda/         # Orders Lambda + IAM role + DynamoDB
│   │   └── lattice/        # Service Network, VPC assoc, Service assoc
│   ├── lambda_src/orders/
│   │   └── handler.py
│   └── tests/
│       └── test_orders_handler.py
├── account-b/              # Inventory service (Account B)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── modules/
│   │   ├── networking/     # VPC, subnets, security groups
│   │   ├── lambda/         # Inventory Lambda v1+v2 + DynamoDB + seed
│   │   └── lattice/        # Service, TGs, Listener, Auth Policy, RAM
│   ├── lambda_src/
│   │   ├── inventory_v1/handler.py
│   │   └── inventory_v2/handler.py
│   └── tests/
│       └── test_inventory_handler.py
└── smoke_test.py           # Integration smoke test (weighted routing)
```

---

## Deployment

**Important:** Account B must be deployed first. Account A depends on outputs from Account B.

### Step 1 — Deploy Account B (Inventory)

Account B requires two inputs: the Account A ID (for the RAM share) and, optionally, the Orders Lambda role ARN (for the IAM auth policy). On the first deploy you won't have the role ARN yet — leave it empty and update it after Account A is deployed.

```bash
cd account-b

terraform init

terraform apply \
  -var="account_a_id=<ACCOUNT_A_ID>"
```

To customise traffic weights (default 80/20):

```bash
terraform apply \
  -var="account_a_id=<ACCOUNT_A_ID>" \
  -var="inventory_v1_weight=70" \
  -var="inventory_v2_weight=30"
```

After apply completes, note the outputs:

```bash
terraform output lattice_service_dns_name   # e.g. inventory-svc-xxxx.vpc-lattice.io
terraform output lattice_service_arn        # arn:aws:vpc-lattice:...
```

You can also capture them in one step:

```bash
INVENTORY_DNS=$(terraform output -raw lattice_service_dns_name)
INVENTORY_ARN=$(terraform output -raw lattice_service_arn)
```

### Step 2 — Deploy Account A (Orders)

Account A requires the Inventory service ARN and DNS name from Step 1, plus the Account B ID.

```bash
cd ../account-a

terraform init

terraform apply \
  -var="account_b_id=<ACCOUNT_B_ID>" \
  -var="inventory_service_arn=${INVENTORY_ARN}" \
  -var="inventory_service_dns=${INVENTORY_DNS}"
```

After apply completes, note the Orders Lambda name:

```bash
terraform output orders_lambda_name          # e.g. orders-lambda-abc123
terraform output orders_lambda_role_arn      # arn:aws:iam::<ACCOUNT_A_ID>:role/...
```

### Step 3 — Update Account B with the Orders Lambda Role ARN

Now that Account A is deployed, update Account B's auth policy so only the Orders Lambda role can call Inventory:

```bash
cd ../account-b

ORDERS_ROLE_ARN=$(cd ../account-a && terraform output -raw orders_lambda_role_arn)

terraform apply \
  -var="account_a_id=<ACCOUNT_A_ID>" \
  -var="orders_lambda_role_arn=${ORDERS_ROLE_ARN}"
```

---

## Invoking the Orders Lambda

### AWS CLI

```bash
ORDERS_LAMBDA=$(cd account-a && terraform output -raw orders_lambda_name)

aws lambda invoke \
  --function-name "${ORDERS_LAMBDA}" \
  --payload '{"order_id":"ord-001"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/orders_response.json \
  && cat /tmp/orders_response.json
```

Terraform also prints a ready-to-run command:

```bash
cd account-a && terraform output orders_lambda_invoke_command
```

Example successful response:

```json
{
  "statusCode": 200,
  "body": {
    "order_id": "ord-001",
    "book": { "item_id": "dune-001", "title": "Dune" },
    "inventory": {
      "item_id": "dune-001",
      "quantity": 42,
      "available": true,
      "version": "v1"
    }
  }
}
```

Seed order IDs you can use: `ord-001`, `ord-002`, `ord-003`.

---

## Running the Smoke Test

The smoke test invokes the Orders Lambda multiple times and prints the v1/v2 version distribution to verify weighted routing.

```bash
# Install dependencies (boto3 is usually already present)
pip install boto3

# Run with defaults (10 invocations, function name from ORDERS_LAMBDA_NAME env var)
ORDERS_LAMBDA_NAME=$(cd account-a && terraform output -raw orders_lambda_name)
python smoke_test.py --function-name "${ORDERS_LAMBDA_NAME}"

# Run more invocations for a better statistical sample
python smoke_test.py --function-name "${ORDERS_LAMBDA_NAME}" --count 50
```

Expected output (approximate):

```
Version distribution (10 successful invocations):
  v1 :   8 / 10  ( 80.0%)  ████████████████████████████████████████
  v2 :   2 / 10  ( 20.0%)  ██████████

Expected: ~80% v1 / ~20% v2  (configured weights)
✓ Smoke test passed — all invocations succeeded.
```

---

## Running Unit Tests

Tests use `pytest` and `moto` to mock AWS services locally — no real AWS credentials needed.

### Install test dependencies

```bash
# Account B (Inventory Lambda tests)
pip install pytest moto boto3

# Account A (Orders Lambda tests)
pip install pytest moto boto3 requests responses
```

### Run Inventory tests (Account B)

```bash
cd account-b
python -m pytest tests/ -v
```

### Run Orders tests (Account A)

```bash
cd account-a
python -m pytest tests/ -v
```

### Run all tests from the project root

```bash
python -m pytest account-a/tests/ account-b/tests/ -v
```

---

## Teardown

Destroy in reverse order — Account A first, then Account B.

```bash
# 1. Destroy Account A
cd account-a
terraform destroy \
  -var="account_b_id=<ACCOUNT_B_ID>" \
  -var="inventory_service_arn=${INVENTORY_ARN}" \
  -var="inventory_service_dns=${INVENTORY_DNS}"

# 2. Destroy Account B
cd ../account-b
terraform destroy \
  -var="account_a_id=<ACCOUNT_A_ID>"
```

Destroying Account A first removes the Service Network association and the Orders Lambda role, which prevents dependency conflicts when Account B's RAM share and auth policy are removed.

---

## Variable Reference

### Account B (`account-b/variables.tf`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `account_a_id` | yes | — | AWS Account ID for Account A (used for RAM share) |
| `orders_lambda_role_arn` | no | `""` | Orders Lambda IAM role ARN (used in Lattice auth policy) |
| `aws_region` | no | `us-east-1` | AWS region |
| `inventory_v1_weight` | no | `80` | Traffic weight for Inventory v1 |
| `inventory_v2_weight` | no | `20` | Traffic weight for Inventory v2 |

### Account A (`account-a/variables.tf`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `account_b_id` | yes | — | AWS Account ID for Account B (used for RAM share acceptance) |
| `inventory_service_arn` | no | `""` | Lattice Inventory service ARN (from Account B output) |
| `inventory_service_dns` | no | `""` | Lattice Inventory service DNS name (from Account B output) |
| `ram_share_arn` | no | `""` | RAM resource share ARN from Account B |
| `aws_region` | no | `us-east-1` | AWS region |

---

## Key Outputs

### Account B

| Output | Description |
|---|---|
| `lattice_service_dns_name` | DNS hostname for the Inventory Lattice service |
| `lattice_service_arn` | ARN of the Inventory Lattice service |

### Account A

| Output | Description |
|---|---|
| `orders_lambda_name` | Name of the Orders Lambda function |
| `orders_lambda_role_arn` | IAM role ARN — provide this to Account B for the auth policy |
| `service_network_arn` | ARN of the VPC Lattice Service Network |
| `orders_lambda_invoke_command` | Ready-to-run AWS CLI invocation command |
