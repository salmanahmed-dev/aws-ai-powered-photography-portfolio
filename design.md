# Design and Architecture

## System Architecture Overview

The AI-Powered Photography Portfolio is built using a serverless architecture on AWS, following modern cloud-native design principles. The system is designed for scalability, performance, and cost-effectiveness.

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CloudFront    │    │   API Gateway    │    │     Lambda      │
│   (Global CDN)  │◄──►│  (REST API)      │◄──►│  (Processing)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│       S3        │    │    DynamoDB      │    │   Rekognition   │
│ (Static Assets) │    │   (Metadata)     │    │  (AI Analysis)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Component Architecture

### Frontend Layer
- **Static Web Application**: HTML5, CSS3, Vanilla JavaScript
- **Responsive Design**: Mobile-first approach with CSS Grid and Flexbox
- **Progressive Enhancement**: Works without JavaScript for basic functionality
- **Client-Side Routing**: Hash-based routing for SPA-like experience

### API Layer
- **API Gateway**: RESTful endpoints with CORS configuration
- **Authentication**: Client-side session management with localStorage
- **Error Handling**: Comprehensive error responses with proper HTTP status codes
- **Rate Limiting**: Built-in throttling and request validation

### Processing Layer
- **Lambda Functions**: Event-driven serverless compute
- **AI Integration**: Amazon Rekognition for image analysis
- **Asynchronous Processing**: S3 event triggers for image processing
- **Error Recovery**: Dead letter queues and retry mechanisms

### Data Layer
- **S3 Buckets**: Multi-bucket strategy for different data types
- **DynamoDB**: NoSQL database with optimized access patterns
- **CloudFront**: Global CDN with edge caching
- **Data Lifecycle**: Automated archival and cleanup policies

## Detailed Component Design

### S3 Bucket Strategy

#### 1. Intake Bucket (`photo-portfolio-intake-{id}`)
- **Purpose**: Temporary storage for uploaded images
- **Lifecycle**: Images deleted after processing
- **Triggers**: Lambda function on object creation
- **Security**: Private bucket with signed URLs

#### 2. Gallery Bucket (`photo-portfolio-img-{id}`)
- **Purpose**: Processed images for public display
- **Lifecycle**: Long-term storage with intelligent tiering
- **Access**: Public read through CloudFront
- **Organization**: Categorized folder structure

#### 3. Archive Bucket (`photo-portfolio-archive-{id}`)
- **Purpose**: Original image backup and compliance
- **Lifecycle**: Glacier transition after 30 days
- **Access**: Admin-only for recovery scenarios
- **Retention**: Long-term archival strategy

### DynamoDB Schema Design

#### Primary Table: `photography-images`
```json
{
  "imageId": "user-12345678",           // Partition Key
  "filename": "street-photo.jpg",
  "title": "Urban Architecture",
  "gallery": "street",                 // GSI Partition Key
  "imageUrl": "/gallery/street-photo.jpg",
  "uploadDate": "2025-06-25T10:30:00Z", // GSI Sort Key
  "description": "AI-generated description",
  "aiLabels": ["building", "urban", "architecture"],
  "subjects": ["building", "street"],
  "themes": ["urban", "architectural"],
  "featured": false,
  "hasFaces": false,
  "faceCount": 0,
  "hasText": false,
  "detectedText": null,
  "confidenceScores": {"building": 95.2},
  "originalFormat": "JPEG",
  "processingMethod": "Enhanced AI Analysis"
}
```

#### Global Secondary Index: `gallery-uploadDate-index`
- **Partition Key**: `gallery`
- **Sort Key**: `uploadDate`
- **Purpose**: Efficient category-based queries with date sorting

### Lambda Function Architecture

#### Image Processor Function
```python
# Enhanced AI Image Processing Pipeline
def lambda_handler(event, context):
    # 1. Parse S3 event trigger
    # 2. Download image from intake bucket
    # 3. Perform comprehensive AI analysis
    # 4. Generate dynamic categories and descriptions
    # 5. Upload processed image to gallery bucket
    # 6. Store metadata in DynamoDB
    # 7. Archive original image
    # 8. Invalidate CloudFront cache
    # 9. Clean up intake bucket
```

**AI Analysis Pipeline**:
1. **Label Detection**: 50+ labels with confidence scores
2. **Face Analysis**: Detection, counting, demographics
3. **Text Recognition**: OCR for text in images
4. **Subject Extraction**: Key elements identification
5. **Theme Analysis**: Mood and style detection
6. **Dynamic Categorization**: Intelligent category assignment
7. **Description Generation**: Natural language descriptions

### API Gateway Design

#### Endpoints Structure
```
/prod/api/
├── images                    # GET: List all images
├── galleries                 # GET: List galleries with counts
├── stats                     # GET: Portfolio statistics
├── upload                    # POST: Get presigned upload URL
└── admin/
    ├── update               # POST: Update image metadata
    └── delete               # POST: Delete image
```

#### Authentication Strategy
- **Client-Side Sessions**: localStorage with 24-hour expiration
- **Role-Based Access**: Admin vs Demo user permissions
- **API Security**: Input validation and sanitization
- **CORS Configuration**: Proper cross-origin resource sharing

## Security Architecture

### Authentication and Authorization
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Login     │───►│   Session   │───►│    API      │
│   Page      │    │  Validation │    │   Access    │
└─────────────┘    └─────────────┘    └─────────────┘
```

#### User Roles and Permissions
- **Admin User**: Full CRUD operations, featured image management
- **Demo User**: Upload-only access, view permissions
- **Public User**: Read-only portfolio viewing

#### Security Measures
- **HTTPS Everywhere**: TLS 1.2+ for all communications
- **Input Validation**: Server-side validation for all inputs
- **SQL Injection Prevention**: Parameterized queries and NoSQL
- **XSS Protection**: Content Security Policy headers
- **CSRF Protection**: SameSite cookies and token validation

### IAM Security Model

#### Lambda Execution Role
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::photo-portfolio-*/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/photography-images*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "rekognition:DetectLabels",
        "rekognition:DetectFaces",
        "rekognition:DetectText"
      ],
      "Resource": "*"
    }
  ]
}
```

## Performance Architecture

### Caching Strategy
- **CloudFront CDN**: Global edge caching for images and static assets
- **Browser Caching**: Appropriate cache headers for different content types
- **API Caching**: DynamoDB DAX for microsecond latency (optional)
- **Client-Side Caching**: localStorage for session and metadata

### Optimization Techniques
- **Image Optimization**: Automatic format selection and compression
- **Lazy Loading**: Progressive image loading for better UX
- **Code Splitting**: Modular JavaScript for faster initial load
- **Minification**: CSS and JavaScript compression
- **Gzip Compression**: Server-side compression for text assets

### Scalability Design
- **Auto-Scaling**: Lambda concurrency and DynamoDB on-demand
- **Load Distribution**: CloudFront global distribution
- **Database Sharding**: Partition key design for even distribution
- **Async Processing**: Event-driven architecture for decoupling

## Data Flow Architecture

### Image Upload Flow
```
User Upload → S3 Intake → Lambda Trigger → AI Analysis → 
DynamoDB Storage → S3 Gallery → CloudFront Cache → User View
```

### Detailed Processing Pipeline
1. **Client Upload**: Presigned URL upload to intake bucket
2. **S3 Event**: Object creation triggers Lambda function
3. **AI Processing**: Rekognition analysis and categorization
4. **Data Storage**: Metadata stored in DynamoDB
5. **Image Processing**: Optimized image stored in gallery bucket
6. **Cache Invalidation**: CloudFront cache updated
7. **Cleanup**: Original file archived and intake cleaned

### API Data Flow
```
Client Request → API Gateway → Lambda Function → 
DynamoDB Query → Response Processing → Client Response
```

## Monitoring and Observability

### Logging Strategy
- **CloudWatch Logs**: Centralized logging for all components
- **Structured Logging**: JSON format for better searchability
- **Log Levels**: DEBUG, INFO, WARN, ERROR with appropriate filtering
- **Correlation IDs**: Request tracing across services

### Metrics and Monitoring
- **Custom Metrics**: Business-specific KPIs and performance indicators
- **AWS X-Ray**: Distributed tracing for request flow analysis
- **CloudWatch Dashboards**: Real-time system health visualization
- **Alarms**: Proactive alerting for system issues

### Health Checks
- **API Health**: Endpoint availability and response time monitoring
- **Database Health**: DynamoDB performance and throttling metrics
- **Storage Health**: S3 bucket access and error rate monitoring
- **CDN Health**: CloudFront distribution performance metrics

## Disaster Recovery and Backup

### Backup Strategy
- **Automated Backups**: DynamoDB point-in-time recovery
- **Cross-Region Replication**: S3 cross-region replication for critical data
- **Version Control**: S3 versioning for accidental deletion protection
- **Archive Strategy**: Glacier storage for long-term retention

### Recovery Procedures
- **RTO Target**: 4 hours for full system recovery
- **RPO Target**: 1 hour maximum data loss
- **Failover Strategy**: Multi-region deployment capability
- **Testing Schedule**: Quarterly disaster recovery testing

## Cost Optimization

### Cost Management Strategy
- **Pay-per-Use**: Serverless architecture minimizes idle costs
- **Storage Optimization**: Intelligent tiering and lifecycle policies
- **Compute Optimization**: Right-sized Lambda functions
- **CDN Optimization**: Efficient caching and compression

### Cost Monitoring
- **AWS Cost Explorer**: Regular cost analysis and optimization
- **Budget Alerts**: Proactive cost monitoring and alerting
- **Resource Tagging**: Detailed cost allocation and tracking
- **Usage Analytics**: Data-driven optimization decisions

This architecture provides a robust, scalable, and cost-effective solution for the AI-powered photography portfolio while maintaining high performance and security standards.
