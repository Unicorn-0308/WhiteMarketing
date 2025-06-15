import asana
from fastapi import FastAPI, Request, Response, status
import hmac
import hashlib
from datetime import datetime as dt
from requests import request

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
        'resource': event.get('resource', {}),
        'resource_type': event.get('resource', {}).get('resource_type'),
        'parent': event.get('parent', {}).get('gid') if event.get('parent') else None,
        'created_at': event.get('created_at'),
        'user': event.get('user', {}).get('gid') if event.get('user') else None
    }

    if event.get('resource_type') == 'attachments':
        return event_info

    if event.get('action') == 'deleted':
        global_exporter.collection.delete_one({"gid": event_info["resource"]["gid"]})
        global_exporter.index_model.delete([event_info["resource"]["gid"]], namespace=pinecone_info["env"])
    elif event.get('action') in ['added', 'changed', 'removed']:
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

        if event.get('action') == 'added' and event.get('resource_type') == 'project':
            request("get", f"https://whitemarketing.onrender.com/establish-webhook/{event.get('resource').get('gid')}")

    return event_info


@app.get('/export-all')
async def export_all(response: Response):
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


@app.get('/establish-all')
async def establish_all(response: Response):
    try:
        log_info("API: Starting to establish webhooks for projects")
        projects = global_exporter.collection.find({
            "name": {
                "$regex": "^\\d{3}"
            },
            "resource_type": "project"
        })

        total_projects = 0
        success_projects = 0
        for project in projects:
            log_info(f"API: Starting establish-webhook request for project {project.get('name', '')}")
            response = request('get', f"https://whitemarketing.onrender.com/establish-webhook/{project.get('gid', '')}")
            if response.status_code != 200:
                log_error(f"API: Failed to establish webhook for project {project.get('name', '')}", response.content)
            else:
                log_info(f"API: Establish-webhooks completed. Success: {project.get('name', '')}")
                success_projects += 1
            total_projects += 1
        log_info(f"API: Success to establish webhooks for projects. Success {success_projects}/{total_projects}")

        log_info("API: Starting to establish webhooks for workspaces")
        workspaces = global_exporter.collection.find({'resource_type': 'workspace'})
        total_workspaces = 0
        success_workspaces = 0
        for workspace in workspaces:
            log_info(f"API: Starting establish-webhook request for workspace {workspace.get('name', '')}")
            response = request('get', f"https://whitemarketing.onrender.com/establish-webhook/{workspace.get('gid', '')}")
            if response.status_code != 200:
                log_error(f"API: Failed to establish webhook for workspace {workspace.get('name', '')}", response.content)
            else:
                log_info(f"API: Establish-webhooks completed. Success: {workspace.get('name', '')}")
                success_workspaces += 1
            total_workspaces += 1
        log_info(f"API: Success to establish webhooks for workspaces. Success {success_workspaces}/{total_workspaces}")

        return {
            'status': 'success',
            'projects': f"Success {success_projects}/{total_projects}",
            'workspaces': f"Success {success_workspaces}/{total_workspaces}",
        }

    except Exception as e:
        log_error("API: Failed to establish webhooks", e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {}

@app.get("/establish-webhook/{gid}")
async def establish_webhook(gid: str, request: Request, response: Response):
    try:
        if not gid:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                'status': 'error',
                'message': 'Missing resource parameter'
            }
        log_info(f"API: Starting establish-webhook request for {gid}")

        # Get all resources from MongoDB
        resource = global_exporter.collection.find_one({
            "gid": gid
        })

        if not resource:
            log_error(f"API: Resource {gid} not found in database")
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                'status': 'error',
                'message': f'Resource {gid} not found'
            }

        gid = resource.get('gid')

        server_url = request.base_url

        webhooks_api = asana.WebhooksApi(api_client)

        if 'webhook' in resource and 'gid' in resource['webhook']:
            try:
                webhooks_api.delete_webhook(resource["webhook"]["gid"])
            except Exception as e:
                log_error("Error while deleting old webhook", e)

        try:
            # Create webhook target URL
            webhook_url = f"{server_url}webhook/{gid}"

            # Create webhook using Asana API
            webhook_data = {
                'resource': gid,
                'target': webhook_url
            }
            if resource.get('resource_type') == 'workspace':
                webhook_data.update({
                    'filters': [{
                        "resource_type": "project",
                        "action": "changed"
                      }, {
                        "resource_type": "project",
                        "action": "added"
                      }, {
                        "resource_type": "project",
                        "action": "deleted"
                      }, {
                        "resource_type": "project",
                        "action": "removed"
                      }, {
                        "resource_type": "team_membership",
                        "action": "added"
                      }, {
                        "resource_type": "team_membership",
                        "action": "removed"
                      }]
                })

            # Use the webhooks API to create webhook
            res = get_response(webhooks_api.create_webhook, {'data': webhook_data}, {}, full_payload=True)

            # Extract webhook info
            webhook_gid = res["data"]["gid"]

            # Get the X-Hook-Secret from response headers (this would typically be in the response)
            # Note: The actual X-Hook-Secret might be returned differently by the Asana API
            x_hook_secret = res.get('X-Hook-Secret', '')  # Adjust this based on actual API response

            # Update resource in MongoDB with webhook info
            webhook_info = {
                'gid': webhook_gid,
                'x_hook_secret': x_hook_secret,
                'target_url': webhook_url,
                'created_at': dt.now()
            }

            global_exporter.collection.update_one(
                {'gid': gid},
                {'$set': {'webhook': webhook_info}}
            )

            log_info(f"API: Successfully established webhook for resource {gid}")

        except Exception as e:
            error_msg = str(e)
            log_error(f"API: Failed to establish webhook for resource({resource.get('resource_type', '')}) ({gid}): {error_msg}", e)
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return {
                'status': 'error',
                'message': f"API: Failed to establish webhook for resource {str(e)}"
            }

        summary = {
            'status': 'completed'
        }

        log_info(f"API: Establish-webhooks completed. Success: {gid}")
        response.status_code = status.HTTP_200_OK
        return summary

    except Exception as e:
        log_error("API: Failed to establish webhooks", e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            'status': 'error',
            'message': f'Failed to establish webhooks: {str(e)}'
        }

@app.post('/webhook/{gid}')
async def webhook_handler(gid: str, request: Request, response: Response):
    """API endpoint to handle incoming webhooks"""
    try:
        secret = request.headers.get('X-Hook-Secret', '')
        if secret:
            response.headers['X-Hook-Secret'] = secret
            return {'status': 'success'}

        # Get resource GID from query parameters
        if not gid:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                'status': 'error',
                'message': 'Missing resource parameter'
            }

        log_info(f"API: Received webhook for resource {gid}")

        # Get resource from MongoDB
        resource = global_exporter.collection.find_one({
            'gid': gid
        })

        if not resource:
            log_error(f"API: Resource {gid} not found in database")
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                'status': 'error',
                'message': f'Resource {gid} not found'
            }

        # Get webhook info
        webhook_info = resource.get('webhook')
        if not webhook_info:
            log_error(f"API: No webhook info found for resource {gid}")
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                'status': 'error',
                'message': f'No webhook info found for resource {gid}'
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
                    log_error(f"API: Invalid webhook signature for resource {gid}")
                    response.status_code = status.HTTP_401_UNAUTHORIZED
                    return {
                        'status': 'error',
                        'message': 'Invalid webhook signature'
                    }
            else:
                log_error(f"API: Missing webhook signature for resource {gid}")
                response.status_code = status.HTTP_401_UNAUTHORIZED
                return {
                    'status': 'error',
                    'message': 'Missing webhook signature'
                }

        # Process webhook events
        events = payload.get('events', [])
        log_info(f"API: Processing {len(events)} events for resource {gid}")

        processed_events = []
        for event in events:
            try:
                event_info = process_event(event)

                processed_events.append(event_info)

                # Here you could add logic to update your database based on the webhook event
                # For example, re-fetch and update the changed resource

                log_info(f"API: Processed event {event_info['type']}.{event_info['action']} for {event_info['resource_type']} {event_info['resource']['gid']}")

            except Exception as e:
                log_error(f"API: Failed to process event for resource {gid}", e)

        # Log webhook processing completion
        log_info(f"API: Successfully processed webhook for resource {gid} with {len(processed_events)} events")

        return {
            'status': 'success',
            'message': f'Webhook processed successfully',
            'resource_gid': gid,
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