import asana
from fastapi import FastAPI, Request, Response, status
import hmac
import hashlib
from datetime import datetime as dt
import asyncio
import os

from db.export_asana_comprehensive import (
    AsanaExporter,
    expand_data,
    log_info,
    log_error,
    get_response,
    api_client,
    global_exporter
)
from db.slite_combined_export import main
from config import pinecone_info

# ==================== FLASK API SERVER ====================

# Create Flask app
app = FastAPI()

def process_event(event):
    # Extract event information
    event_info = {
        'type': event.get('type'),
        'action': event.get('action'),
        'resource': event.get('resource', {}).get('gid'),
        'resource_type': event.get('resource', {}).get('resource_type'),
        'parent': event.get('parent', {}).get('gid') if event.get('parent') else None,
        'created_at': event.get('created_at'),
        'user': event.get('user', {}).get('gid') if event.get('user') else None
    }

    if event.get('action') == 'deleted':
        global_exporter.collection.delete_one({"gid": event_info["resource"]})
        global_exporter.index_model.delete([event_info["resource"]], namespace=pinecone_info["env"])
    elif event.get('action') == 'added' or event.get('action') == 'changed':
        if event_info['parent']:
            parent = global_exporter.collection.find_one({"gid": event_info["parent"]})
            parent_clients = parent.get('clients', [])
        else:
            parent_clients = []

        expand_data(
            data=event.get('resource', {}),
            space=global_exporter.space,
            collection=global_exporter.collection,
            index_model=global_exporter.index_model,
            parent_clients=parent_clients,
            first=True
        )

    return event_info


@app.get('/export-all')
def export_all(response: Response):
    """API endpoint to run the complete export process"""
    try:
        log_info("API: Starting export-all request")

        # Run the export process
        summary = global_exporter.run_export()

        # Return summary
        result = {
            'status': 'success',
            'message': 'Export completed successfully',
            'data': summary
        }

        log_info("API: Export-all completed successfully")
        return result

    except Exception as e:
        log_error("API: Failed to complete export-all", e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            'status': 'error',
            'message': f'Export failed: {str(e)}'
        }


@app.get("/establish-webhook/{project_gid}")
async def establish_webhook(project_gid: str, request: Request, response: Response):
    try:
        if not project_gid:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                'status': 'error',
                'message': 'Missing project parameter'
            }
        log_info(f"API: Starting establish-webhook request for project {project_gid}")

        # Get all projects from MongoDB
        project = global_exporter.collection.find_one({
            "gid": project_gid
        })

        if not project:
            log_error(f"API: Project {project_gid} not found in database")
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                'status': 'error',
                'message': f'Project {project_gid} not found'
            }

        project_gid = project.get('gid')
        project_name = project.get('name', 'Unknown')

        server_url = request.base_url

        webhooks_api = asana.WebhooksApi(api_client)

        if 'webhook' in project and 'gid' in project['webhook']:
            try:
                webhooks_api.delete_webhook(project["webhook"]["gid"])
            except Exception as e:
                log_error("Error while deleting old webhook", e)

        try:
            # Create webhook target URL
            webhook_url = f"{server_url}webhook/{project_gid}"

            # Create webhook using Asana API
            webhook_data = {
                'resource': project_gid,
                'target': webhook_url
            }

            # Use the webhooks API to create webhook
            res = get_response(webhooks_api.create_webhook, {'data': webhook_data}, {}, full_payload=True)

            # Extract webhook info
            webhook_gid = res["data"]["gid"]

            # Get the X-Hook-Secret from response headers (this would typically be in the response)
            # Note: The actual X-Hook-Secret might be returned differently by the Asana API
            x_hook_secret = res.get('X-Hook-Secret', '')  # Adjust this based on actual API response

            # Update project in MongoDB with webhook info
            webhook_info = {
                'gid': webhook_gid,
                'x_hook_secret': x_hook_secret,
                'target_url': webhook_url,
                'created_at': dt.now()
            }

            global_exporter.collection.update_one(
                {'gid': project_gid, 'resource_type': 'project'},
                {'$set': {'webhook': webhook_info}}
            )

            log_info(f"API: Successfully established webhook for project {project_name} ({project_gid})")

        except Exception as e:
            error_msg = str(e)
            log_error(f"API: Failed to establish webhook for project {project_name} ({project_gid}): {error_msg}", e)
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {
                'status': 'error',
                'message': f"API: Failed to establish webhook for project {str(e)}"
            }

        summary = {
            'status': 'completed'
        }

        log_info(f"API: Establish-webhooks completed. Success: {project_gid}")
        response.status_code = status.HTTP_200_OK
        return summary

    except Exception as e:
        log_error("API: Failed to establish webhooks", e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            'status': 'error',
            'message': f'Failed to establish webhooks: {str(e)}'
        }

@app.post('/webhook/{project_gid}')
async def webhook_handler(project_gid: str, request: Request, response: Response):
    """API endpoint to handle incoming webhooks"""
    try:
        secret = request.headers.get('X-Hook-Secret', '')
        if secret:
            response.headers['X-Hook-Secret'] = secret
            return {'status': 'success'}

        # Get project GID from query parameters
        if not project_gid:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                'status': 'error',
                'message': 'Missing project parameter'
            }

        log_info(f"API: Received webhook for project {project_gid}")

        # Get project from MongoDB
        project = global_exporter.collection.find_one({
            'gid': project_gid,
            'resource_type': 'project'
        })

        if not project:
            log_error(f"API: Project {project_gid} not found in database")
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                'status': 'error',
                'message': f'Project {project_gid} not found'
            }

        # Get webhook info
        webhook_info = project.get('webhook')
        if not webhook_info:
            log_error(f"API: No webhook info found for project {project_gid}")
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                'status': 'error',
                'message': f'No webhook info found for project {project_gid}'
            }

        payload = await request.json()

        # Verify webhook signature
        x_hook_secret = webhook_info.get('x_hook_secret', '')
        if x_hook_secret:
            # Get the signature from headers
            signature = request.headers.get('X-Hook-Signature', '')

            if signature:
                # Verify the signature using HMAC-SHA256
                expected_signature = hmac.new(
                    x_hook_secret.encode('utf-8'),
                    await request.body(),
                    hashlib.sha256
                ).hexdigest()

                if not hmac.compare_digest(signature, expected_signature):
                    log_error(f"API: Invalid webhook signature for project {project_gid}")
                    response.status_code = status.HTTP_401_UNAUTHORIZED
                    return {
                        'status': 'error',
                        'message': 'Invalid webhook signature'
                    }
            else:
                log_error(f"API: Missing webhook signature for project {project_gid}")
                response.status_code = status.HTTP_401_UNAUTHORIZED
                return {
                    'status': 'error',
                    'message': 'Missing webhook signature'
                }

        # Process webhook events
        events = payload.get('events', [])
        log_info(f"API: Processing {len(events)} events for project {project_gid}")

        processed_events = []
        for event in events:
            try:
                event_info = process_event(event)

                processed_events.append(event_info)

                # Here you could add logic to update your database based on the webhook event
                # For example, re-fetch and update the changed resource

                log_info(f"API: Processed event {event_info['type']}.{event_info['action']} for {event_info['resource_type']} {event_info['resource']}")

            except Exception as e:
                log_error(f"API: Failed to process event for project {project_gid}", e)

        # Log webhook processing completion
        log_info(f"API: Successfully processed webhook for project {project_gid} with {len(processed_events)} events")

        return {
            'status': 'success',
            'message': f'Webhook processed successfully',
            'project_gid': project_gid,
            'events_processed': len(processed_events),
            'events': processed_events
        }

    except Exception as e:
        log_error("API: Failed to process webhook", e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            'status': 'error',
            'message': f'Failed to process webhook: {str(e)}'
        }


@app.get('/health')
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': dt.now().isoformat(),
        'service': 'Asana Export API'
    }

@app.get("/update-slite")
async def update_slite():
    num_updated = await main()
    return {
        'status': 'success',
        'updated': num_updated
    }

if __name__ == "__main__":
    pass