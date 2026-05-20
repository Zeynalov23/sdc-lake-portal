.PHONY: up down init bootstrap

# Bootstrap: run once before anything else
# S3 bucket already exists manually — just need the DynamoDB lock table
bootstrap:
	@echo "--- Step 1: Create S3 state bucket (idempotent) ---"
	aws s3api head-bucket --bucket sdc-lake-terraform-state 2>/dev/null || \
		( aws s3api create-bucket \
		    --bucket sdc-lake-terraform-state \
		    --region eu-west-1 \
		    --create-bucket-configuration LocationConstraint=eu-west-1 && \
		  aws s3api put-bucket-versioning \
		    --bucket sdc-lake-terraform-state \
		    --versioning-configuration Status=Enabled && \
		  aws s3api put-public-access-block \
		    --bucket sdc-lake-terraform-state \
		    --public-access-block-configuration \
		    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true )
	@echo "--- Step 2: Init with S3 backend ---"
	cd infra-persistent && terraform init -reconfigure
	@echo "--- Step 3: Apply all persistent infra ---"
	cd infra-persistent && terraform apply -auto-approve
	@echo "--- Bootstrap complete ---"

# Start of session: bring up the cluster (~15 min)
up:
	@echo "--- Bringing up EKS cluster ---"
	cd infra-cluster && terraform init && terraform apply -auto-approve
	@echo ""
	@echo "--- Configure kubectl ---"
	cd infra-cluster && terraform output -raw configure_kubectl | bash
	@echo ""
	@echo "--- Cluster ready ---"
	kubectl get nodes

# End of session: tear down the cluster (~8 min)
# Deletes Gateway resources first so the NLB is removed from AWS
# before Terraform tries to delete the VPC (otherwise VPC delete hangs)
down:
	@echo "--- Deleting Gateway resources so NLB deprovisions first ---"
	kubectl delete gateway --all -n envoy-gateway-system --ignore-not-found || true
	kubectl delete gateway --all -n app --ignore-not-found || true
	@echo "--- Waiting 30s for NLB to be removed from AWS ---"
	sleep 30
	@echo "--- Tearing down EKS cluster (persistent infra untouched) ---"
	cd infra-cluster && terraform destroy -auto-approve
	@echo "--- Done. DynamoDB / S3 / SQS / ECR / Secrets still intact ---"

# Re-init both modules (run after pulling repo on a new machine)
init:
	cd infra-persistent && terraform init
	cd infra-cluster && terraform init