# Design Document: VPC Lattice Demo

## Overview

Two AWS accounts communicate via VPC Lattice without VPC Peering. Account B owns the Inventory service (Lambda + DynamoDB), registers it in VPC Lattice, and shares it via AWS RAM. Account A owns the Orders service (Lambda + DynamoDB), connects to the shared Inventory service through a Service Network, and calls it by DNS name with SigV4 signing.

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

---

## Architecture

### Cross-Account Flow

1. Account B creates a VPC Lattice **Service** with two Target Groups (v1, v2) and a Listener with weighted routing 80/20.
2. Account B shares the Service with Account A via **AWS RAM** (by account ID).
3. Account A creates a VPC Lattice **Service Network**, associates VPC-A with it, and accepts the RAM-shared Service.
4. The Orders Lambda in Account A resolves the Inventory Service DNS name, signs the request with SigV4, and sends an HTTP request.
5. VPC Lattice validates the IAM Auth Policy on the Inventory Service — only the Orders Lambda role from Account A is allowed.
6. Traffic is routed to v1 or v2 according to the configured weights.

### Authentication Flow

```
Orders Lambda
  │
  ├─ signs request with SigV4 (boto3 / aws-requests-auth)
  │   service=vpc-lattice-svcs, region=us-east-1
  │
  ▼
VPC Lattice Endpoint
  │
  ├─ validates IAM signature
  ├─ checks Auth Policy: aws:PrincipalArn == orders-lambda-role ARN
  │
  ▼
Inventory Lambda (v1 or v2, per weights)
```
