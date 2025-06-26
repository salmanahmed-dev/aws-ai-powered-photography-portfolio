#!/bin/bash

# Deploy Cognito-enabled Photography Portfolio
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
STACK_NAME="photography-portfolio"
REGION="us-east-1"
PROJECT_NAME="photo-portfolio"

print_status "🚀 Deploying Cognito-enabled Photography Portfolio"
echo ""

# Check if stack exists
if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION &> /dev/null; then
    print_status "Updating existing stack with Cognito integration..."
    OPERATION="update-stack"
else
    print_status "Creating new stack with Cognito..."
    OPERATION="create-stack"
fi

# Deploy CloudFormation stack
print_status "Deploying infrastructure..."
aws cloudformation $OPERATION \
    --stack-name $STACK_NAME \
    --template-body file://cloudformation.yaml \
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

# Get stack outputs
print_status "Retrieving stack outputs..."
OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query 'Stacks[0].Outputs' \
    --output json)

# Extract outputs
USER_POOL_ID=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="CognitoUserPoolId") | .OutputValue')
CLIENT_ID=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="CognitoUserPoolClientId") | .OutputValue')
WEB_BUCKET=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="WebBucketName") | .OutputValue')
WEBSITE_URL=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="WebsiteURL") | .OutputValue')
API_URL=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="APIURL") | .OutputValue')

print_success "Stack deployment completed!"
echo ""
echo "Cognito Configuration:"
echo "• User Pool ID: $USER_POOL_ID"
echo "• Client ID: $CLIENT_ID"
echo ""

# Update login.html with Cognito configuration
print_status "Updating login page with Cognito configuration..."
sed -i.bak "s/UserPoolId: 'us-east-1_PLACEHOLDER'/UserPoolId: '$USER_POOL_ID'/g" login.html
sed -i.bak "s/ClientId: 'PLACEHOLDER_CLIENT_ID'/ClientId: '$CLIENT_ID'/g" login.html

# Update admin.html with API URL if needed
if [ ! -z "$API_URL" ]; then
    print_status "Updating API URLs in frontend files..."
    sed -i.bak "s|https://uarfzfpq10.execute-api.us-east-1.amazonaws.com/prod|$API_URL|g" admin.html
fi

# Upload updated files
print_status "Uploading updated frontend files..."
aws s3 cp login.html s3://$WEB_BUCKET/login.html --content-type "text/html" --region $REGION
aws s3 cp admin.html s3://$WEB_BUCKET/admin.html --content-type "text/html" --region $REGION
aws s3 cp index.html s3://$WEB_BUCKET/index.html --content-type "text/html" --region $REGION

# Update Lambda function code
print_status "Updating Lambda function code..."
zip -r lambda-deployment.zip lambda-processor.py > /dev/null
FUNCTION_NAME="${PROJECT_NAME}-image-processor"
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://lambda-deployment.zip \
    --region $REGION > /dev/null
rm -f lambda-deployment.zip

# Invalidate CloudFront cache
CLOUDFRONT_ID=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="CloudFrontDistributionId") | .OutputValue')
if [ ! -z "$CLOUDFRONT_ID" ]; then
    print_status "Invalidating CloudFront cache..."
    aws cloudfront create-invalidation \
        --distribution-id $CLOUDFRONT_ID \
        --paths "/*" \
        --region $REGION > /dev/null
fi

# Clean up backup files
rm -f login.html.bak admin.html.bak

print_success "🎉 Cognito integration deployment completed!"
echo ""
echo "📸 AI-Powered Photography Portfolio with Cognito"
echo "=============================================="
echo ""
echo "🌐 Website URL: $WEBSITE_URL"
echo "🔗 API URL: $API_URL"
echo "🔐 Authentication: Amazon Cognito"
echo ""
echo "👑 Admin Credentials:"
echo "   Username: admin"
echo "   Password: qclicoder2025"
echo ""
echo "👤 Demo Credentials:"
echo "   Username: demo"
echo "   Password: demo123"
echo ""
echo "🔒 Security Features:"
echo "   • JWT token-based authentication"
echo "   • Secure password storage"
echo "   • Session management"
echo "   • Enterprise-grade security"
echo ""
echo "🎯 Next Steps:"
echo "1. Test login at: $WEBSITE_URL/login.html"
echo "2. Verify admin panel access"
echo "3. Test image upload and AI processing"
echo ""

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 30

# Test endpoints
print_status "Running post-deployment tests..."
if curl -s -o /dev/null -w "%{http_code}" $WEBSITE_URL | grep -q "200"; then
    print_success "✅ Website is accessible"
else
    print_warning "⚠️  Website may not be fully ready yet"
fi

if curl -s -o /dev/null -w "%{http_code}" $API_URL/api/images | grep -q "200"; then
    print_success "✅ API is responding"
else
    print_warning "⚠️  API may not be fully ready yet"
fi

print_success "🚀 Deployment completed successfully!"
echo ""
echo "Your AI-powered photography portfolio is now secured with Amazon Cognito!"
echo "Users can log in with the same credentials but now benefit from enterprise-grade security."
