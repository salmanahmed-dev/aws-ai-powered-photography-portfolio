# Deployment Guide

## Prerequisites

### AWS Account Requirements
- AWS Account with administrative access
- AWS CLI installed and configured
- Appropriate IAM permissions for:
  - S3 (CreateBucket, PutObject, GetObject, DeleteObject)
  - Lambda (CreateFunction, UpdateFunctionCode, InvokeFunction)
  - API Gateway (CreateRestApi, CreateDeployment)
  - DynamoDB (CreateTable, PutItem, GetItem, Query)
  - CloudFront (CreateDistribution, CreateInvalidation)
  - Rekognition (DetectLabels, DetectFaces, DetectText)
  - IAM (CreateRole, AttachRolePolicy)

### Local Development Environment
- AWS CLI v2.0 or higher
- Python 3.9 or higher (for Lambda development)
- Node.js 16+ (for deployment scripts, optional)
- Git (for version control)

### Domain and SSL (Optional)
- Custom domain name
- SSL certificate in AWS Certificate Manager
- Route 53 hosted zone (recommended)

## Deployment Options

### Option 1: One-Click CloudFormation Deployment (Recommended)

This is the fastest way to deploy the entire solution.

```bash
# Clone the repository
git clone <repository-url>
cd Final-Quack-The-Code-Challenge

# Deploy using CloudFormation
aws cloudformation create-stack \
  --stack-name photography-portfolio \
  --template-body file://cloudformation.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=ProjectName,ParameterValue=my-portfolio

# Monitor deployment progress
aws cloudformation describe-stacks \
  --stack-name photography-portfolio \
  --query 'Stacks[0].StackStatus'
```

### Option 2: Manual Step-by-Step Deployment

For learning purposes or custom configurations.

#### Step 1: Create S3 Buckets

```bash
# Generate unique identifier
UNIQUE_ID=$(date +%s | tail -c 9)

# Create buckets
aws s3 mb s3://photo-portfolio-intake-${UNIQUE_ID}
aws s3 mb s3://photo-portfolio-img-${UNIQUE_ID}
aws s3 mb s3://photo-portfolio-archive-${UNIQUE_ID}
aws s3 mb s3://photo-portfolio-web-${UNIQUE_ID}

# Configure bucket policies
aws s3api put-bucket-policy \
  --bucket photo-portfolio-img-${UNIQUE_ID} \
  --policy file://policies/gallery-bucket-policy.json

# Enable versioning for archive bucket
aws s3api put-bucket-versioning \
  --bucket photo-portfolio-archive-${UNIQUE_ID} \
  --versioning-configuration Status=Enabled
```

#### Step 2: Create DynamoDB Table

```bash
# Create main table
aws dynamodb create-table \
  --table-name photography-images \
  --attribute-definitions \
    AttributeName=imageId,AttributeType=S \
    AttributeName=gallery,AttributeType=S \
    AttributeName=uploadDate,AttributeType=S \
  --key-schema \
    AttributeName=imageId,KeyType=HASH \
  --global-secondary-indexes \
    IndexName=gallery-uploadDate-index,KeySchema=[{AttributeName=gallery,KeyType=HASH},{AttributeName=uploadDate,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5} \
  --provisioned-throughput \
    ReadCapacityUnits=5,WriteCapacityUnits=5
```

#### Step 3: Create IAM Role for Lambda

```bash
# Create trust policy
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name PhotoPortfolio-AI-Role \
  --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name PhotoPortfolio-AI-Role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam put-role-policy \
  --role-name PhotoPortfolio-AI-Role \
  --policy-name PhotoPortfolioPolicy \
  --policy-document file://policies/lambda-execution-policy.json
```

#### Step 4: Deploy Lambda Function

```bash
# Package Lambda function
zip -r lambda-processor.zip lambda-processor.py

# Create Lambda function
aws lambda create-function \
  --function-name photo-portfolio-image-processor \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT-ID:role/PhotoPortfolio-AI-Role \
  --handler lambda-processor.lambda_handler \
  --zip-file fileb://lambda-processor.zip \
  --timeout 120 \
  --memory-size 1024 \
  --environment Variables='{
    "INTAKE_BUCKET":"photo-portfolio-intake-'${UNIQUE_ID}'",
    "GALLERY_BUCKET":"photo-portfolio-img-'${UNIQUE_ID}'",
    "ARCHIVE_BUCKET":"photo-portfolio-archive-'${UNIQUE_ID}'",
    "DYNAMODB_TABLE":"photography-images"
  }'
```

#### Step 5: Configure S3 Event Triggers

```bash
# Create notification configuration
cat > notification-config.json << EOF
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "ImageProcessorTrigger",
      "LambdaFunctionArn": "arn:aws:lambda:REGION:ACCOUNT-ID:function:photo-portfolio-image-processor",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "Suffix", "Value": ".jpg"},
            {"Name": "Suffix", "Value": ".jpeg"},
            {"Name": "Suffix", "Value": ".png"}
          ]
        }
      }
    }
  ]
}
EOF

# Apply notification configuration
aws s3api put-bucket-notification-configuration \
  --bucket photo-portfolio-intake-${UNIQUE_ID} \
  --notification-configuration file://notification-config.json
```

#### Step 6: Create API Gateway

```bash
# Create REST API
API_ID=$(aws apigateway create-rest-api \
  --name photo-portfolio-api \
  --query 'id' --output text)

# Get root resource ID
ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[0].id' --output text)

# Create API resources and methods
# (Detailed API Gateway setup commands...)
```

#### Step 7: Create CloudFront Distribution

```bash
# Create distribution configuration
cat > distribution-config.json << EOF
{
  "CallerReference": "photo-portfolio-$(date +%s)",
  "Comment": "Photography Portfolio CDN",
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 2,
    "Items": [
      {
        "Id": "S3-photo-portfolio-web-${UNIQUE_ID}",
        "DomainName": "photo-portfolio-web-${UNIQUE_ID}.s3.amazonaws.com",
        "S3OriginConfig": {
          "OriginAccessIdentity": ""
        }
      },
      {
        "Id": "S3-photo-portfolio-img-${UNIQUE_ID}",
        "DomainName": "photo-portfolio-img-${UNIQUE_ID}.s3.amazonaws.com",
        "S3OriginConfig": {
          "OriginAccessIdentity": ""
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-photo-portfolio-web-${UNIQUE_ID}",
    "ViewerProtocolPolicy": "redirect-to-https",
    "TrustedSigners": {
      "Enabled": false,
      "Quantity": 0
    },
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": {"Forward": "none"}
    },
    "MinTTL": 0
  },
  "Enabled": true,
  "PriceClass": "PriceClass_100"
}
EOF

# Create distribution
aws cloudfront create-distribution \
  --distribution-config file://distribution-config.json
```

#### Step 8: Deploy Frontend Files

```bash
# Upload static files to web bucket
aws s3 cp index.html s3://photo-portfolio-web-${UNIQUE_ID}/ --content-type "text/html"
aws s3 cp admin.html s3://photo-portfolio-web-${UNIQUE_ID}/ --content-type "text/html"
aws s3 cp login.html s3://photo-portfolio-web-${UNIQUE_ID}/ --content-type "text/html"

# Configure bucket for static website hosting
aws s3 website s3://photo-portfolio-web-${UNIQUE_ID} \
  --index-document index.html \
  --error-document error.html
```

## Configuration

### Environment Variables

Update the following environment variables in your Lambda function:

```bash
INTAKE_BUCKET=photo-portfolio-intake-{unique-id}
GALLERY_BUCKET=photo-portfolio-img-{unique-id}
ARCHIVE_BUCKET=photo-portfolio-archive-{unique-id}
DYNAMODB_TABLE=photography-images
CLOUDFRONT_DISTRIBUTION_ID={distribution-id}
```

### API Gateway Configuration

Update the API base URL in your frontend files:

```javascript
// In admin.html and any other files making API calls
const API_BASE = 'https://{api-id}.execute-api.{region}.amazonaws.com/prod';
```

### Custom Domain Setup (Optional)

If you want to use a custom domain:

```bash
# Create certificate (must be in us-east-1 for CloudFront)
aws acm request-certificate \
  --domain-name yourdomain.com \
  --validation-method DNS \
  --region us-east-1

# Update CloudFront distribution with custom domain
aws cloudfront update-distribution \
  --id {distribution-id} \
  --distribution-config file://custom-domain-config.json

# Create Route 53 record
aws route53 change-resource-record-sets \
  --hosted-zone-id {zone-id} \
  --change-batch file://route53-changes.json
```

## Post-Deployment Configuration

### 1. Test the System

```bash
# Test API endpoints
curl https://{api-id}.execute-api.{region}.amazonaws.com/prod/api/images

# Test image upload
# (Use the admin panel to upload a test image)

# Verify CloudFront distribution
curl -I https://{distribution-domain}/
```

### 2. Configure Monitoring

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name PhotoPortfolio \
  --dashboard-body file://monitoring/dashboard.json

# Set up alarms
aws cloudwatch put-metric-alarm \
  --alarm-name "PhotoPortfolio-HighErrorRate" \
  --alarm-description "High error rate in photo portfolio" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

### 3. Set Up Backup

```bash
# Enable DynamoDB point-in-time recovery
aws dynamodb update-continuous-backups \
  --table-name photography-images \
  --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

# Configure S3 cross-region replication (optional)
aws s3api put-bucket-replication \
  --bucket photo-portfolio-archive-${UNIQUE_ID} \
  --replication-configuration file://replication-config.json
```

## Verification Steps

### 1. Frontend Verification
- [ ] Portfolio loads at CloudFront URL
- [ ] Three category sections display correctly
- [ ] Images load and display properly
- [ ] Full-screen viewing works
- [ ] Mobile responsiveness verified

### 2. Authentication Verification
- [ ] Login page accessible
- [ ] Admin login works (admin/qclicoder2025)
- [ ] Demo login works (demo/demo1234)
- [ ] Session management functioning
- [ ] Logout functionality working

### 3. Admin Panel Verification
- [ ] Admin panel loads for authenticated users
- [ ] Image upload functionality works
- [ ] AI processing completes successfully
- [ ] Image editing and deletion work
- [ ] Role-based permissions enforced

### 4. API Verification
- [ ] All API endpoints responding
- [ ] Image listing returns data
- [ ] Upload presigned URLs working
- [ ] Admin operations functioning
- [ ] Error handling working properly

### 5. Performance Verification
- [ ] Page load times < 3 seconds
- [ ] Image processing < 30 seconds
- [ ] API response times < 2 seconds
- [ ] CDN caching working
- [ ] Mobile performance acceptable

## Troubleshooting

### Common Issues

#### 1. Lambda Function Timeout
```bash
# Increase timeout
aws lambda update-function-configuration \
  --function-name photo-portfolio-image-processor \
  --timeout 300
```

#### 2. CORS Issues
```bash
# Update API Gateway CORS settings
aws apigateway put-method-response \
  --rest-api-id {api-id} \
  --resource-id {resource-id} \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters method.response.header.Access-Control-Allow-Origin=true
```

#### 3. S3 Permission Issues
```bash
# Update bucket policy
aws s3api put-bucket-policy \
  --bucket {bucket-name} \
  --policy file://updated-bucket-policy.json
```

#### 4. DynamoDB Throttling
```bash
# Increase provisioned capacity
aws dynamodb update-table \
  --table-name photography-images \
  --provisioned-throughput ReadCapacityUnits=10,WriteCapacityUnits=10
```

### Logs and Debugging

```bash
# View Lambda logs
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/photo-portfolio

# View specific log stream
aws logs get-log-events \
  --log-group-name /aws/lambda/photo-portfolio-image-processor \
  --log-stream-name {stream-name}

# View API Gateway logs
aws logs describe-log-groups --log-group-name-prefix API-Gateway-Execution-Logs
```

## Maintenance

### Regular Tasks
- Monitor CloudWatch metrics and alarms
- Review and optimize costs monthly
- Update Lambda function code as needed
- Rotate access keys and credentials
- Review and update security policies
- Monitor storage usage and costs

### Updates and Patches
- Keep Lambda runtime updated
- Update dependencies in Lambda functions
- Review and update IAM policies
- Monitor AWS service updates
- Update documentation as needed

## Cost Optimization

### Monitoring Costs
```bash
# Set up billing alerts
aws budgets create-budget \
  --account-id {account-id} \
  --budget file://budget-config.json

# Review cost and usage
aws ce get-cost-and-usage \
  --time-period Start=2025-01-01,End=2025-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

### Optimization Strategies
- Use S3 Intelligent Tiering for cost optimization
- Implement DynamoDB on-demand billing for variable workloads
- Optimize Lambda memory allocation based on usage
- Use CloudFront caching to reduce origin requests
- Implement lifecycle policies for S3 objects

## Security Best Practices

### Regular Security Tasks
- Review IAM policies and permissions
- Monitor CloudTrail logs for suspicious activity
- Update and rotate access keys
- Review S3 bucket policies and ACLs
- Monitor for security vulnerabilities
- Keep all components updated

### Security Monitoring
```bash
# Enable CloudTrail
aws cloudtrail create-trail \
  --name photo-portfolio-trail \
  --s3-bucket-name {logging-bucket}

# Enable GuardDuty
aws guardduty create-detector --enable
```

This deployment guide provides comprehensive instructions for setting up the AI-Powered Photography Portfolio in any AWS account. Choose the deployment method that best fits your needs and follow the verification steps to ensure everything is working correctly.
