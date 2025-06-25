import json
import boto3
import uuid
from datetime import datetime

# Initialize AWS services
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')
cloudfront = boto3.client('cloudfront')

# Configuration
INTAKE_BUCKET = 'photo-portfolio-intake-20cc1a45'
GALLERY_BUCKET = 'photo-portfolio-img-20cc1a45'
ARCHIVE_BUCKET = 'photo-portfolio-archive-20cc1a45'
TABLE_NAME = 'photography-images'
CLOUDFRONT_DISTRIBUTION_ID = 'E20SASFFP7LKC2'

def lambda_handler(event, context):
    """
    Enhanced AI image processor with detailed analysis and dynamic categories
    """
    try:
        # Parse S3 event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        print(f"Processing: {key}")
        
        # Download the image
        response = s3.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()
        
        # Enhanced AI Analysis
        ai_analysis = analyze_image_enhanced(image_data)
        
        # Generate gallery filename with dynamic category
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        gallery_filename = f"{ai_analysis['category']}-{key}"
        
        # Upload to gallery bucket
        s3.put_object(
            Bucket=GALLERY_BUCKET,
            Key=f'gallery/{gallery_filename}',
            Body=image_data,
            ContentType=get_content_type(key)
        )
        
        # Archive original
        s3.copy_object(
            CopySource={'Bucket': bucket, 'Key': key},
            Bucket=ARCHIVE_BUCKET,
            Key=f'archive/{key}'
        )
        
        # Add to database with enhanced details
        add_to_database_enhanced(gallery_filename, ai_analysis, key)
        
        # Invalidate CloudFront cache
        invalidate_cloudfront()
        
        # Clean up intake bucket
        s3.delete_object(Bucket=bucket, Key=key)
        
        print(f"Success: {key} -> gallery/{gallery_filename} (Category: {ai_analysis['category']})")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Image processed successfully',
                'category': ai_analysis['category'],
                'filename': gallery_filename,
                'aiAnalysis': ai_analysis
            })
        }
        
    except Exception as e:
        print(f"Error processing {key}: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def analyze_image_enhanced(image_data):
    """
    Enhanced AI analysis with detailed descriptions and dynamic categorization
    """
    try:
        # Get comprehensive labels
        labels_response = rekognition.detect_labels(
            Image={'Bytes': image_data},
            MaxLabels=50,
            MinConfidence=60
        )
        
        # Get text detection
        text_response = None
        try:
            text_response = rekognition.detect_text(
                Image={'Bytes': image_data}
            )
        except:
            pass
        
        # Get face detection
        faces_response = None
        try:
            faces_response = rekognition.detect_faces(
                Image={'Bytes': image_data},
                Attributes=['ALL']
            )
        except:
            pass
        
        # Process labels
        labels = []
        confidence_scores = {}
        for label in labels_response['Labels']:
            label_name = label['Name'].lower()
            labels.append(label_name)
            confidence_scores[label_name] = label['Confidence']
        
        print(f"AI Labels detected: {labels[:10]}...")  # Log first 10 labels
        
        # Enhanced categorization with dynamic categories
        category = determine_dynamic_category(labels, confidence_scores, faces_response, text_response)
        
        # Generate detailed description
        description = generate_detailed_description(labels, confidence_scores, faces_response, text_response, category)
        
        # Extract key subjects and themes
        subjects = extract_key_subjects(labels, confidence_scores)
        themes = extract_themes(labels, confidence_scores)
        
        return {
            'category': category,
            'description': description,
            'labels': labels,
            'confidence_scores': confidence_scores,
            'subjects': subjects,
            'themes': themes,
            'has_faces': faces_response is not None and len(faces_response.get('FaceDetails', [])) > 0,
            'has_text': text_response is not None and len(text_response.get('TextDetections', [])) > 0,
            'face_count': len(faces_response.get('FaceDetails', [])) if faces_response else 0,
            'detected_text': extract_text_content(text_response) if text_response else None
        }
        
    except Exception as e:
        print(f"AI analysis error: {str(e)} - using fallback")
        return {
            'category': 'general',
            'description': 'AI-processed photography',
            'labels': ['photography'],
            'confidence_scores': {},
            'subjects': [],
            'themes': [],
            'has_faces': False,
            'has_text': False,
            'face_count': 0,
            'detected_text': None
        }

def determine_dynamic_category(labels, confidence_scores, faces_response, text_response):
    """
    Determine category dynamically based on comprehensive analysis
    """
    try:
        # Define category keywords with weights
        category_keywords = {
            'portraits': {
                'keywords': ['person', 'face', 'human', 'man', 'woman', 'people', 'portrait', 'selfie', 'head', 'smile'],
                'weight': 1.0
            },
            'nature': {
                'keywords': ['tree', 'forest', 'mountain', 'lake', 'sky', 'cloud', 'landscape', 'water', 'plant', 'flower', 'animal', 'wildlife', 'sunset', 'sunrise', 'ocean', 'beach', 'river'],
                'weight': 1.0
            },
            'street': {
                'keywords': ['city', 'building', 'street', 'urban', 'architecture', 'car', 'road', 'sign', 'traffic', 'downtown', 'sidewalk', 'crosswalk'],
                'weight': 1.0
            },
            'food': {
                'keywords': ['food', 'meal', 'restaurant', 'dining', 'plate', 'dish', 'cooking', 'kitchen', 'drink', 'beverage', 'coffee', 'bread', 'fruit'],
                'weight': 0.9
            },
            'architecture': {
                'keywords': ['building', 'architecture', 'structure', 'bridge', 'monument', 'church', 'tower', 'skyscraper', 'facade', 'interior'],
                'weight': 0.9
            },
            'events': {
                'keywords': ['wedding', 'party', 'celebration', 'concert', 'festival', 'ceremony', 'gathering', 'performance', 'stage'],
                'weight': 0.8
            },
            'sports': {
                'keywords': ['sport', 'game', 'ball', 'field', 'stadium', 'athlete', 'competition', 'team', 'player', 'exercise'],
                'weight': 0.8
            },
            'travel': {
                'keywords': ['vacation', 'tourism', 'landmark', 'destination', 'sightseeing', 'adventure', 'journey', 'exploration'],
                'weight': 0.8
            },
            'abstract': {
                'keywords': ['pattern', 'texture', 'design', 'art', 'creative', 'artistic', 'geometric', 'abstract', 'color'],
                'weight': 0.7
            },
            'technology': {
                'keywords': ['computer', 'phone', 'device', 'screen', 'electronic', 'digital', 'technology', 'gadget'],
                'weight': 0.7
            }
        }
        
        # Calculate scores for each category
        category_scores = {}
        
        for category, config in category_keywords.items():
            score = 0
            keyword_matches = 0
            
            for keyword in config['keywords']:
                for label in labels:
                    if keyword in label:
                        confidence = confidence_scores.get(label, 0)
                        score += (confidence / 100) * config['weight']
                        keyword_matches += 1
            
            # Bonus for multiple keyword matches
            if keyword_matches > 1:
                score *= (1 + (keyword_matches - 1) * 0.1)
            
            category_scores[category] = score
        
        # Special handling for faces
        if faces_response and len(faces_response.get('FaceDetails', [])) > 0:
            face_count = len(faces_response['FaceDetails'])
            category_scores['portraits'] = category_scores.get('portraits', 0) + (face_count * 20)
        
        # Special handling for text
        if text_response and len(text_response.get('TextDetections', [])) > 0:
            category_scores['street'] = category_scores.get('street', 0) + 10
            category_scores['architecture'] = category_scores.get('architecture', 0) + 5
        
        # Find the best category
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            best_score = category_scores[best_category]
            
            # Only use the category if it has a reasonable score
            if best_score > 5:
                print(f"AI Category: {best_category} (score: {best_score:.1f})")
                return best_category
        
        # Fallback to general if no strong category match
        print("AI Category: general (no strong match)")
        return 'general'
        
    except Exception as e:
        print(f"Category determination error: {e}")
        return 'general'

def generate_detailed_description(labels, confidence_scores, faces_response, text_response, category):
    """
    Generate detailed, natural description of the image
    """
    try:
        # Get top labels by confidence
        top_labels = sorted(
            [(label, confidence_scores.get(label, 0)) for label in labels],
            key=lambda x: x[1],
            reverse=True
        )[:8]
        
        # Build description components
        description_parts = []
        
        # Category-specific opening
        category_openings = {
            'portraits': 'Portrait photography featuring',
            'nature': 'Nature photography capturing',
            'street': 'Street photography showcasing',
            'food': 'Food photography displaying',
            'architecture': 'Architectural photography highlighting',
            'events': 'Event photography documenting',
            'sports': 'Sports photography capturing',
            'travel': 'Travel photography featuring',
            'abstract': 'Abstract photography exploring',
            'technology': 'Technology photography showing',
            'general': 'Photography featuring'
        }
        
        description_parts.append(category_openings.get(category, 'Photography featuring'))
        
        # Add main subjects
        main_subjects = []
        for label, confidence in top_labels[:3]:
            if confidence > 80:
                main_subjects.append(label)
        
        if main_subjects:
            if len(main_subjects) == 1:
                description_parts.append(f" {main_subjects[0]}")
            elif len(main_subjects) == 2:
                description_parts.append(f" {main_subjects[0]} and {main_subjects[1]}")
            else:
                description_parts.append(f" {', '.join(main_subjects[:-1])}, and {main_subjects[-1]}")
        
        # Add face information
        if faces_response and len(faces_response.get('FaceDetails', [])) > 0:
            face_count = len(faces_response['FaceDetails'])
            if face_count == 1:
                description_parts.append(" with one person")
            else:
                description_parts.append(f" with {face_count} people")
        
        # Add environmental context
        environment_labels = [label for label, conf in top_labels if conf > 70 and 
                            label in ['outdoor', 'indoor', 'daytime', 'night', 'sunset', 'sunrise']]
        if environment_labels:
            description_parts.append(f" in {environment_labels[0]} setting")
        
        # Add text information
        if text_response and len(text_response.get('TextDetections', [])) > 0:
            description_parts.append(" with visible text elements")
        
        # Combine and clean up
        description = ''.join(description_parts)
        
        # Add additional context from high-confidence labels
        additional_context = []
        for label, confidence in top_labels[3:6]:
            if confidence > 75 and label not in description.lower():
                additional_context.append(label)
        
        if additional_context:
            description += f". Features {', '.join(additional_context)}"
        
        description += "."
        
        return description
        
    except Exception as e:
        print(f"Description generation error: {e}")
        return f"AI-processed {category} photography with detected elements"

def extract_key_subjects(labels, confidence_scores):
    """
    Extract key subjects from the image
    """
    try:
        # Filter for high-confidence subject labels
        subject_keywords = ['person', 'animal', 'vehicle', 'building', 'plant', 'food', 'object']
        subjects = []
        
        for label in labels:
            confidence = confidence_scores.get(label, 0)
            if confidence > 75:
                for keyword in subject_keywords:
                    if keyword in label.lower():
                        subjects.append(label)
                        break
        
        return subjects[:5]  # Return top 5 subjects
        
    except Exception as e:
        print(f"Subject extraction error: {e}")
        return []

def extract_themes(labels, confidence_scores):
    """
    Extract themes and moods from the image
    """
    try:
        theme_keywords = {
            'urban': ['city', 'street', 'building', 'urban', 'downtown'],
            'natural': ['nature', 'outdoor', 'landscape', 'sky', 'water'],
            'social': ['people', 'group', 'crowd', 'gathering', 'party'],
            'peaceful': ['calm', 'serene', 'quiet', 'peaceful', 'tranquil'],
            'active': ['sport', 'action', 'movement', 'dynamic', 'energy'],
            'artistic': ['art', 'creative', 'design', 'pattern', 'aesthetic']
        }
        
        themes = []
        for theme, keywords in theme_keywords.items():
            score = 0
            for keyword in keywords:
                for label in labels:
                    if keyword in label.lower():
                        score += confidence_scores.get(label, 0)
            
            if score > 100:  # Threshold for theme inclusion
                themes.append(theme)
        
        return themes
        
    except Exception as e:
        print(f"Theme extraction error: {e}")
        return []

def extract_text_content(text_response):
    """
    Extract readable text from the image
    """
    try:
        if not text_response or 'TextDetections' not in text_response:
            return None
        
        text_items = []
        for detection in text_response['TextDetections']:
            if detection['Type'] == 'LINE' and detection['Confidence'] > 80:
                text_items.append(detection['DetectedText'])
        
        return text_items[:5] if text_items else None
        
    except Exception as e:
        print(f"Text extraction error: {e}")
        return None

def get_content_type(filename):
    """
    Get content type based on file extension
    """
    extension = filename.lower().split('.')[-1]
    content_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif'
    }
    return content_types.get(extension, 'image/jpeg')

def add_to_database_enhanced(filename, ai_analysis, original_filename):
    """
    Add enhanced image data to DynamoDB
    """
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        # Generate unique ID
        image_id = f"user-{str(uuid.uuid4())[:8]}"
        
        # Create title from filename and AI analysis
        base_name = filename.replace(f'{ai_analysis["category"]}-', '').replace('.jpg', '').replace('.jpeg', '').replace('.png', '').replace('_', ' ')
        
        # Enhanced title based on subjects
        if ai_analysis['subjects']:
            main_subject = ai_analysis['subjects'][0]
            title = f"{ai_analysis['category'].title()} - {main_subject.title()} Photography"
        else:
            title = f"{ai_analysis['category'].title()} Photography - {base_name.title()}"
        
        # Add to database with enhanced fields
        table.put_item(
            Item={
                'imageId': image_id,
                'filename': filename,
                'title': title,
                'gallery': ai_analysis['category'],
                'imageUrl': f'/gallery/{filename}',
                'uploadDate': datetime.now().isoformat(),
                'description': ai_analysis['description'],
                'aiLabels': ai_analysis['labels'],
                'confidenceScores': ai_analysis['confidence_scores'],
                'subjects': ai_analysis['subjects'],
                'themes': ai_analysis['themes'],
                'hasFaces': ai_analysis['has_faces'],
                'hasText': ai_analysis['has_text'],
                'faceCount': ai_analysis['face_count'],
                'detectedText': ai_analysis['detected_text'],
                'originalFilename': original_filename,
                'originalFormat': original_filename.split('.')[-1].upper(),
                'featured': False,
                'processingMethod': 'Enhanced AI Analysis'
            }
        )
        
        print(f"Added to database: {image_id} (Category: {ai_analysis['category']})")
        
    except Exception as e:
        print(f"Database error: {str(e)}")
        raise

def invalidate_cloudfront():
    """
    Invalidate CloudFront cache
    """
    try:
        cloudfront.create_invalidation(
            DistributionId=CLOUDFRONT_DISTRIBUTION_ID,
            InvalidationBatch={
                'Paths': {
                    'Quantity': 2,
                    'Items': ['/', '/api/images']
                },
                'CallerReference': f'enhanced-processor-{int(datetime.now().timestamp())}'
            }
        )
        print("CloudFront cache invalidated")
    except Exception as e:
        print(f"CloudFront invalidation warning: {str(e)}")
