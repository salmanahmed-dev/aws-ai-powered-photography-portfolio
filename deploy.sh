#!/bin/bash

# AI-Powered Photography Portfolio Deployment Script
# This script deploys the complete solution to AWS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="photography-portfolio"
TEMPLATE_FILE="cloudformation.yaml"
REGION="us-east-1"
PROJECT_NAME="photo-portfolio"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    # Check if template exists
    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_error "CloudFormation template not found: $TEMPLATE_FILE"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to validate CloudFormation template
validate_template() {
    print_status "Validating CloudFormation template..."
    
    if aws cloudformation validate-template --template-body file://$TEMPLATE_FILE --region $REGION > /dev/null; then
        print_success "Template validation passed"
    else
        print_error "Template validation failed"
        exit 1
    fi
}

# Function to deploy the stack
deploy_stack() {
    print_status "Deploying CloudFormation stack: $STACK_NAME"
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION &> /dev/null; then
        print_status "Stack exists, updating..."
        OPERATION="update-stack"
    else
        print_status "Creating new stack..."
        OPERATION="create-stack"
    fi
    
    # Deploy the stack
    aws cloudformation $OPERATION \
        --stack-name $STACK_NAME \
        --template-body file://$TEMPLATE_FILE \
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
        --parameters ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
                    ParameterKey=Environment,ParameterValue=prod \
        --region $REGION
    
    print_status "Waiting for stack deployment to complete..."
    
    if [ "$OPERATION" = "create-stack" ]; then
        aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $REGION
    else
        aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --region $REGION
    fi
    
    print_success "Stack deployment completed successfully"
}

# Function to get stack outputs
get_stack_outputs() {
    print_status "Retrieving stack outputs..."
    
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $REGION \
        --query 'Stacks[0].Outputs' \
        --output json)
    
    # Extract important outputs
    WEBSITE_URL=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="WebsiteURL") | .OutputValue')
    API_URL=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="APIURL") | .OutputValue')
    WEB_BUCKET=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="WebBucketName") | .OutputValue')
    CLOUDFRONT_ID=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="CloudFrontDistributionId") | .OutputValue')
    
    echo ""
    print_success "Deployment completed successfully!"
    echo ""
    echo "📸 AI-Powered Photography Portfolio"
    echo "=================================="
    echo ""
    echo "🌐 Website URL: $WEBSITE_URL"
    echo "🔗 API URL: $API_URL"
    echo "📦 Web Bucket: $WEB_BUCKET"
    echo "☁️  CloudFront ID: $CLOUDFRONT_ID"
    echo ""
    echo "🔐 Login Credentials:"
    echo "   Admin: admin / portfolio2024"
    echo "   Demo:  demo / demo123"
    echo ""
}

# Function to upload frontend files
upload_frontend() {
    print_status "Uploading frontend files to S3..."
    
    # Update API URL in frontend files
    if [ ! -z "$API_URL" ]; then
        print_status "Updating API URLs in frontend files..."
        
        # Create temporary files with updated API URLs
        sed "s|https://uarfzfpq10.execute-api.us-east-1.amazonaws.com/prod|$API_URL|g" index.html > index_updated.html
        sed "s|https://uarfzfpq10.execute-api.us-east-1.amazonaws.com/prod|$API_URL|g" admin.html > admin_updated.html
        
        # Upload updated files
        aws s3 cp index_updated.html s3://$WEB_BUCKET/index.html --content-type "text/html" --region $REGION
        aws s3 cp admin_updated.html s3://$WEB_BUCKET/admin.html --content-type "text/html" --region $REGION
        aws s3 cp login.html s3://$WEB_BUCKET/login.html --content-type "text/html" --region $REGION
        
        # Clean up temporary files
        rm -f index_updated.html admin_updated.html
    else
        # Upload original files
        aws s3 cp index.html s3://$WEB_BUCKET/ --content-type "text/html" --region $REGION
        aws s3 cp admin.html s3://$WEB_BUCKET/ --content-type "text/html" --region $REGION
        aws s3 cp login.html s3://$WEB_BUCKET/ --content-type "text/html" --region $REGION
    fi
    
    print_success "Frontend files uploaded successfully"
}

# Function to update Lambda function code
update_lambda_code() {
    print_status "Updating Lambda function code..."
    
    # Create deployment package
    zip -r lambda-deployment.zip lambda-processor.py
    
    # Update Lambda function
    FUNCTION_NAME="${PROJECT_NAME}-image-processor"
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://lambda-deployment.zip \
        --region $REGION > /dev/null
    
    # Clean up
    rm -f lambda-deployment.zip
    
    print_success "Lambda function code updated"
}

# Function to invalidate CloudFront cache
invalidate_cache() {
    if [ ! -z "$CLOUDFRONT_ID" ]; then
        print_status "Invalidating CloudFront cache..."
        
        aws cloudfront create-invalidation \
            --distribution-id $CLOUDFRONT_ID \
            --paths "/*" \
            --region $REGION > /dev/null
        
        print_success "CloudFront cache invalidation initiated"
    fi
}

# Function to run post-deployment tests
run_tests() {
    print_status "Running post-deployment tests..."
    
    # Test website accessibility
    if curl -s -o /dev/null -w "%{http_code}" $WEBSITE_URL | grep -q "200"; then
        print_success "Website is accessible"
    else
        print_warning "Website may not be fully ready yet"
    fi
    
    # Test API endpoint
    if curl -s -o /dev/null -w "%{http_code}" $API_URL/api/images | grep -q "200"; then
        print_success "API is responding"
    else
        print_warning "API may not be fully ready yet"
    fi
}

# Function to show help
show_help() {
    echo "AI-Powered Photography Portfolio Deployment Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -s, --stack-name NAME   Set stack name (default: photography-portfolio)"
    echo "  -r, --region REGION     Set AWS region (default: us-east-1)"
    echo "  -p, --project-name NAME Set project name (default: photo-portfolio)"
    echo "  --validate-only         Only validate template, don't deploy"
    echo "  --skip-upload           Skip frontend file upload"
    echo "  --skip-lambda           Skip Lambda code update"
    echo ""
    echo "Examples:"
    echo "  $0                      # Deploy with default settings"
    echo "  $0 -s my-portfolio     # Deploy with custom stack name"
    echo "  $0 --validate-only     # Only validate template"
    echo ""
}

# Parse command line arguments
VALIDATE_ONLY=false
SKIP_UPLOAD=false
SKIP_LAMBDA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -s|--stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -p|--project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        --skip-upload)
            SKIP_UPLOAD=true
            shift
            ;;
        --skip-lambda)
            SKIP_LAMBDA=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo ""
    echo "🚀 AI-Powered Photography Portfolio Deployment"
    echo "=============================================="
    echo ""
    
    check_prerequisites
    validate_template
    
    if [ "$VALIDATE_ONLY" = true ]; then
        print_success "Template validation completed. Exiting."
        exit 0
    fi
    
    deploy_stack
    get_stack_outputs
    
    if [ "$SKIP_LAMBDA" = false ]; then
        update_lambda_code
    fi
    
    if [ "$SKIP_UPLOAD" = false ]; then
        upload_frontend
    fi
    
    invalidate_cache
    
    # Wait a moment for services to be ready
    print_status "Waiting for services to be ready..."
    sleep 30
    
    run_tests
    
    echo ""
    print_success "🎉 Deployment completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Visit your portfolio: $WEBSITE_URL"
    echo "2. Login to admin panel: $WEBSITE_URL/login.html"
    echo "3. Upload your first image to test the AI processing"
    echo "4. Customize the portfolio with your own images"
    echo ""
    echo "For troubleshooting, check the deployment guide: deployment-guide.md"
    echo ""
}

# Run main function
main
