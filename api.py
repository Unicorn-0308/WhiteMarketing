import asana
from flask import Flask, request, jsonify, make_response
import hmac
import hashlib
from datetime import datetime as dt
import asyncio
import os
import dotenv
dotenv.load_dotenv()

from db.export_asana_comprehensive import (
    AsanaExporter,
    expand_data,
    log_info,
    log_error,
    get_response,
    api_client
)
from db.slite_combined_export import main
from config import pinecone_info

# ==================== FLASK API SERVER ====================

# Create Flask app
app = Flask(__name__)

# Global AsanaExporter instance
global_exporter = AsanaExporter()


# def setup_global_exporter():
#     """Setup the global exporter instance"""
#     global global_exporter

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

    if event.get('action') == 'delete':
        global_exporter.collection.delete_one({"gid": event_info["resource"]})
        global_exporter.index_model.delete([event_info["resource"]], namespace=pinecone_info["env"])
    elif event.get('action') == 'create' or event.get('action') == 'update':
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


@app.route('/export-all', methods=['GET'])
def export_all():
    """API endpoint to run the complete export process"""
    try:
        log_info("API: Starting export-all request")

        # Setup if not already done
        # setup_global_exporter()

        # Run the export process
        summary = global_exporter.run_export()

        # Return summary
        result = {
            'status': 'success',
            'message': 'Export completed successfully',
            'data': summary
        }

        log_info("API: Export-all completed successfully")
        return jsonify(result), 200

    except Exception as e:
        log_error("API: Failed to complete export-all", e)
        return jsonify({
            'status': 'error',
            'message': f'Export failed: {str(e)}'
        }), 500


@app.route('/establish-webhooks', methods=['GET'])
def establish_webhooks():
    """API endpoint to establish webhooks for all projects"""
    try:
        log_info("API: Starting establish-webhooks request")

        # Setup if not already done
        # setup_global_exporter()

        # Get all projects from MongoDB
        projects_cursor = global_exporter.collection.find({
            "resource_type": "project",
            "name": {"$regex": "^\\d{3}"}  # Only projects starting with 3 digits
        })

        projects = list(projects_cursor)
        log_info(f"API: Found {len(projects)} projects to establish webhooks for")

        success_count = 0
        error_count = 0
        results = []

        # Get the server URL for webhook target
        server_url = request.host_url.rstrip('/')

        for project in projects:
            project_gid = project.get('gid')
            project_name = project.get('name', 'Unknown')

            webhooks_api = asana.WebhooksApi(api_client)

            if 'webhook' in project and 'gid' in project['webhook']:
                try:
                    webhooks_api.delete_webhook(project["webhook"]["gid"])
                except Exception as e:
                    log_error("Error while deleting old webhook", e)

            try:
                # Create webhook target URL
                webhook_url = f"{server_url}/webhook?project={project_gid}"

                # Create webhook using Asana API
                webhook_data = {
                    'resource': project_gid,
                    'target': webhook_url
                }

                # Use the webhooks API to create webhook
                response = get_response(webhooks_api.create_webhook, {'data': webhook_data}, {}, full_payload=True)

                # Extract webhook info
                webhook_gid = response["data"]["gid"]

                # Get the X-Hook-Secret from response headers (this would typically be in the response)
                # Note: The actual X-Hook-Secret might be returned differently by the Asana API
                x_hook_secret = response.get('X-Hook-Secret', '')  # Adjust this based on actual API response

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

                success_count += 1
                results.append({
                    'project_gid': project_gid,
                    'project_name': project_name,
                    'status': 'success',
                    'webhook_gid': webhook_gid
                })

                log_info(f"API: Successfully established webhook for project {project_name} ({project_gid})")

            except Exception as e:
                error_count += 1
                error_msg = str(e)
                results.append({
                    'project_gid': project_gid,
                    'project_name': project_name,
                    'status': 'error',
                    'error': error_msg
                })

                log_error(f"API: Failed to establish webhook for project {project_name} ({project_gid}): {error_msg}",
                          e)

        summary = {
            'status': 'completed',
            'message': f'Webhook establishment completed. Success: {success_count}, Errors: {error_count}',
            'summary': {
                'total_projects': len(projects),
                'success_count': success_count,
                'error_count': error_count
            },
            'results': results
        }

        log_info(f"API: Establish-webhooks completed. Success: {success_count}, Errors: {error_count}")
        return jsonify(summary), 200

    except Exception as e:
        log_error("API: Failed to establish webhooks", e)
        return jsonify({
            'status': 'error',
            'message': f'Failed to establish webhooks: {str(e)}'
        }), 500


@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """API endpoint to handle incoming webhooks"""
    try:
        secret = request.headers.get('X-Hook-Secret', '')
        if secret:
            resp = make_response()
            resp.status_code = 200
            resp.headers['X-Hook-Secret'] = secret
            return resp

        # Get project GID from query parameters
        project_gid = request.args.get('project')
        if not project_gid:
            return jsonify({
                'status': 'error',
                'message': 'Missing project parameter'
            }), 400

        log_info(f"API: Received webhook for project {project_gid}")

        # Setup if not already done
        # setup_global_exporter()

        # Get project from MongoDB
        project = global_exporter.collection.find_one({
            'gid': project_gid,
            'resource_type': 'project'
        })

        if not project:
            log_error(f"API: Project {project_gid} not found in database")
            return jsonify({
                'status': 'error',
                'message': f'Project {project_gid} not found'
            }), 404

        # Get webhook info
        webhook_info = project.get('webhook')
        if not webhook_info:
            log_error(f"API: No webhook info found for project {project_gid}")
            return jsonify({
                'status': 'error',
                'message': f'No webhook info found for project {project_gid}'
            }), 400

        # Verify webhook signature
        x_hook_secret = webhook_info.get('x_hook_secret', '')
        if x_hook_secret:
            # Get the signature from headers
            signature = request.headers.get('X-Hook-Signature', '')

            if signature:
                # Verify the signature using HMAC-SHA256
                payload = request.data
                expected_signature = hmac.new(
                    x_hook_secret.encode('utf-8'),
                    payload,
                    hashlib.sha256
                ).hexdigest()

                if not hmac.compare_digest(signature, expected_signature):
                    log_error(f"API: Invalid webhook signature for project {project_gid}")
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid webhook signature'
                    }), 401
            else:
                log_error(f"API: Missing webhook signature for project {project_gid}")
                return jsonify({
                    'status': 'error',
                    'message': 'Missing webhook signature'
                }), 401

        # Parse webhook payload
        try:
            webhook_data = request.get_json()
        except Exception as e:
            log_error(f"API: Failed to parse webhook JSON for project {project_gid}", e)
            return jsonify({
                'status': 'error',
                'message': 'Invalid JSON payload'
            }), 400

        # Process webhook events
        events = webhook_data.get('events', [])
        log_info(f"API: Processing {len(events)} events for project {project_gid}")

        processed_events = []
        for event in events:
            try:
                event_info = process_event(event)

                processed_events.append(event_info)

                # Here you could add logic to update your database based on the webhook event
                # For example, re-fetch and update the changed resource

                log_info(
                    f"API: Processed event {event_info['type']}.{event_info['action']} for {event_info['resource_type']} {event_info['resource']}")

            except Exception as e:
                log_error(f"API: Failed to process event for project {project_gid}", e)

        # Log webhook processing completion
        log_info(f"API: Successfully processed webhook for project {project_gid} with {len(processed_events)} events")

        return jsonify({
            'status': 'success',
            'message': f'Webhook processed successfully',
            'project_gid': project_gid,
            'events_processed': len(processed_events),
            'events': processed_events
        }), 200

    except Exception as e:
        log_error("API: Failed to process webhook", e)
        return jsonify({
            'status': 'error',
            'message': f'Failed to process webhook: {str(e)}'
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': dt.now().isoformat(),
        'service': 'Asana Export API'
    }), 200

@app.route("/update-slite", methods=["GET"])
def update_slite():
    num_updated = asyncio.run(main())
    return jsonify({
        'status': 'success',
        'updated': num_updated
    }), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)