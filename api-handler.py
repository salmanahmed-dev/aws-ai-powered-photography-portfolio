import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# Table name
TABLE_NAME = 'photography-images'

def decimal_default(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    """
    Main API handler for photography portfolio
    """
    
    # CORS headers for all responses
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Content-Type': 'application/json'
    }
    
    try:
        # Get request details
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        resource = event.get('resource', '')
        
        print(f"API Request: {http_method} {path} (resource: {resource})")
        
        # Handle OPTIONS requests for CORS
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': headers,
                'body': json.dumps({'message': 'CORS preflight successful'})
            }
        
        # Route requests based on path
        if path == '/api/images' or resource == '/api/images':
            if http_method == 'GET':
                return get_images(headers)
            else:
                return {
                    'statusCode': 405,
                    'headers': headers,
                    'body': json.dumps({'error': 'Method not allowed'})
                }
        
        elif path == '/api/galleries' or resource == '/api/galleries':
            if http_method == 'GET':
                return get_galleries(headers)
            else:
                return {
                    'statusCode': 405,
                    'headers': headers,
                    'body': json.dumps({'error': 'Method not allowed'})
                }
        
        elif path.startswith('/api/admin/') or resource.startswith('/api/admin/'):
            return handle_admin_request(event, headers)
        
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': f'Endpoint not found: {path}'})
            }
            
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }

def get_images(headers):
    """Get all images from DynamoDB"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        print("Scanning DynamoDB table for images...")
        response = table.scan()
        
        images = response.get('Items', [])
        print(f"Found {len(images)} images in database")
        
        # Convert Decimal types to float for JSON serialization
        images_json = json.loads(json.dumps(images, default=decimal_default))
        
        print(f"Returning {len(images_json)} images")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'images': images_json,
                'count': len(images_json),
                'status': 'success'
            })
        }
        
    except Exception as e:
        print(f"Error in get_images: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Failed to get images: {str(e)}'})
        }

def get_galleries(headers):
    """Get gallery statistics"""
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        print("Scanning DynamoDB table for gallery statistics...")
        response = table.scan()
        
        images = response.get('Items', [])
        print(f"Found {len(images)} images for gallery analysis")
        
        # Count images by gallery
        galleries = {}
        for image in images:
            gallery = image.get('gallery', 'general')
            galleries[gallery] = galleries.get(gallery, 0) + 1
        
        print(f"Gallery statistics: {galleries}")
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'galleries': galleries,
                'total_images': len(images),
                'status': 'success'
            })
        }
        
    except Exception as e:
        print(f"Error in get_galleries: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Failed to get galleries: {str(e)}'})
        }

def handle_admin_request(event, headers):
    """Handle admin operations"""
    try:
        path = event.get('path', '')
        http_method = event.get('httpMethod', '')
        
        print(f"Admin request: {http_method} {path}")
        
        if path.endswith('/update') and http_method == 'POST':
            return update_image(event, headers)
        elif path.endswith('/delete') and http_method == 'POST':
            return delete_image(event, headers)
        else:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'Admin endpoint not found'})
            }
            
    except Exception as e:
        print(f"Error in handle_admin_request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Admin operation failed: {str(e)}'})
        }

def update_image(event, headers):
    """Update image metadata"""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        image_id = body.get('imageId')
        
        if not image_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'imageId is required'})
            }
        
        table = dynamodb.Table(TABLE_NAME)
        
        # Build update expression
        update_expression = "SET "
        expression_values = {}
        
        if 'title' in body:
            update_expression += "title = :title, "
            expression_values[':title'] = body['title']
        
        if 'description' in body:
            update_expression += "description = :description, "
            expression_values[':description'] = body['description']
        
        if 'gallery' in body:
            update_expression += "gallery = :gallery, "
            expression_values[':gallery'] = body['gallery']
        
        if 'featured' in body:
            update_expression += "featured = :featured, "
            expression_values[':featured'] = body['featured']
        
        # Remove trailing comma and space
        update_expression = update_expression.rstrip(', ')
        
        if not expression_values:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'No valid fields to update'})
            }
        
        # Update the item
        table.update_item(
            Key={'imageId': image_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'Image updated successfully'})
        }
        
    except Exception as e:
        print(f"Error in update_image: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Failed to update image: {str(e)}'})
        }

def delete_image(event, headers):
    """Delete image and its files"""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        image_id = body.get('imageId')
        
        if not image_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'imageId is required'})
            }
        
        table = dynamodb.Table(TABLE_NAME)
        
        # Get image details first
        response = table.get_item(Key={'imageId': image_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'Image not found'})
            }
        
        image = response['Item']
        filename = image.get('filename')
        
        # Delete from S3 if filename exists
        if filename:
            try:
                # Delete from gallery bucket
                s3.delete_object(Bucket='photo-portfolio-img-20cc1a45', Key=filename)
                print(f"Deleted {filename} from gallery bucket")
            except Exception as s3_error:
                print(f"Error deleting from S3: {str(s3_error)}")
        
        # Delete from DynamoDB
        table.delete_item(Key={'imageId': image_id})
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'Image deleted successfully'})
        }
        
    except Exception as e:
        print(f"Error in delete_image: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': f'Failed to delete image: {str(e)}'})
        }
