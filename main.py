import os
import json
import re
from flask import Flask, request, jsonify
from pydantic import BaseModel, ValidationError
from loguru import logger
from kubernetes import client, config
import openai
import subprocess
import yaml
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins='http://localhost:3000')

logger.add("agent.log", rotation="1 MB")

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    answer: str

try:
    config.load_kube_config()
    logger.info("Kubernetes configuration loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Kubernetes configuration: {e}")
    raise

core_v1_api = client.CoreV1Api()
apps_v1_api = client.AppsV1Api()

openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logger.error("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable.")
    raise Exception("OpenAI API key is not set.")

@app.route("/query", methods=["POST"])
def query_kubernetes():
    data = request.get_json()

    try:
        query_request = QueryRequest(**data)
    except ValidationError as e:
        logger.error(f"Request validation error: {e}")
        return jsonify({"error": "Invalid request format"}), 400

    logger.info(f"Received query: {query_request.query}")

    try:
        action = interpret_query(query_request.query)
        logger.info(f"Interpreted action: {action}")

        answer = perform_kubernetes_action(action)
        logger.info(f"Answer: {answer}")

        # Validate response format with Pydantic
        query_response = QueryResponse(query=query_request.query, answer=answer)
        return jsonify(query_response.dict())

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

# Function to interpret the query using GPT-4
def interpret_query(query_text):
    system_prompt = (
        "You are a Kubernetes assistant. Your task is to interpret the user's query and output a JSON object "
        "with two keys: 'action' and 'parameters'. The 'action' must be one of ['count_resources', 'get_status', "
        "'list_resources', 'get_logs', 'describe_resource', 'get_resource_detail']. "
        "If the user's intent does not match any of these actions, set 'action' to 'unknown'. "
        "The 'parameters' should include 'resource_type' (e.g., 'pod', 'deployment', 'service', 'node'), "
        "'resource_name' if applicable, 'namespace' if specified, and any specific 'detail' the user is requesting "
        "(e.g., 'environment_variable', 'mount_path', 'database_name'). "
        "Ensure 'resource_name' is the exact name used in Kubernetes, replacing spaces with hyphens if necessary, and exclude resource type abbreviations like 'svc', 'pod', etc. "
        "Do not include any additional text outside of the JSON object."
    )

    user_prompt = f"User query: {query_text}\nResponse:"

    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0,
        max_tokens=300
    )

    assistant_reply = response.choices[0].message.content.strip()
    logger.debug(f"Assistant reply: {assistant_reply}")

    try:
        action = json.loads(assistant_reply)
        if 'action' not in action or 'parameters' not in action:
            raise ValueError("Invalid format: Missing 'action' or 'parameters' keys.")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse assistant's reply as JSON: {e}")
        raise Exception("Failed to interpret the query.")

    return action

# Function to normalize action types
def normalize_action_type(action_type):
    action_mapping = {
        'count_pods': 'count_resources',
        'count_deployments': 'count_resources',
        'count_nodes': 'count_resources',
        'count_services': 'count_resources',
        'get_pod_status': 'get_status',
        'get_deployment_status': 'get_status',
        'get_service_status': 'get_status',
        'list_pods': 'list_resources',
        'list_deployments': 'list_resources',
        'list_services': 'list_resources',
        'get_pod_logs': 'get_logs',
        'describe_pod': 'describe_resource',
        'describe_deployment': 'describe_resource',
        'get_pod_details': 'describe_resource',
        'get_resource_detail': 'get_resource_detail',
    }
    return action_mapping.get(action_type, action_type)

# Enhanced function to normalize resource types
def normalize_resource_type(resource_type):
    resource_type_mapping = {
        'pods': 'pod',
        'pod': 'pod',
        'po': 'pod',
        'p': 'pod',
        'deployments': 'deployment',
        'deployment': 'deployment',
        'deploy': 'deployment',
        'dep': 'deployment',
        'services': 'service',
        'service': 'service',
        'svc': 'service',
        'nodes': 'node',
        'node': 'node',
        'no': 'node',
        'configmaps': 'configmap',
        'configmap': 'configmap',
        'cm': 'configmap',
        'secrets': 'secret',
        'secret': 'secret',
        'sec': 'secret',
        'namespaces': 'namespace',
        'namespace': 'namespace',
        'ns': 'namespace',
        'endpoints': 'endpoint',
        'endpoint': 'endpoint',
        'ep': 'endpoint',
        'ingresses': 'ingress',
        'ingress': 'ingress',
        'ing': 'ingress',
        'persistentvolumeclaims': 'persistentvolumeclaim',
        'persistentvolumeclaim': 'persistentvolumeclaim',
        'pvc': 'persistentvolumeclaim',
        'persistentvolumes': 'persistentvolume',
        'persistentvolume': 'persistentvolume',
        'pv': 'persistentvolume',
        'replicasets': 'replicaset',
        'replicaset': 'replicaset',
        'rs': 'replicaset',
        'statefulsets': 'statefulset',
        'statefulset': 'statefulset',
        'sts': 'statefulset',
        'daemonsets': 'daemonset',
        'daemonset': 'daemonset',
        'ds': 'daemonset',
        'jobs': 'job',
        'job': 'job',
        'cronjobs': 'cronjob',
        'cronjob': 'cronjob',
        'cj': 'cronjob',
        'roles': 'role',
        'role': 'role',
        'rolebindings': 'rolebinding',
        'rolebinding': 'rolebinding',
        'rb': 'rolebinding',
        'clusterroles': 'clusterrole',
        'clusterrole': 'clusterrole',
        'cr': 'clusterrole',
        'clusterrolebindings': 'clusterrolebinding',
        'clusterrolebinding': 'clusterrolebinding',
        'crb': 'clusterrolebinding',
        'registry': 'deployment',  # Added mapping for 'registry'
        'persistent volume': 'persistentvolume',  # Mapping for 'persistent volume'
    }
    return resource_type_mapping.get(resource_type.lower(), resource_type.lower())

# Function to normalize resource names
def normalize_resource_name(resource_name):
    resource_name = resource_name.lower()
    resource_name = resource_name.replace(' svc', '').replace(' service', '')
    resource_name = resource_name.replace(' pod', '').replace(' deployment', '')
    resource_name = resource_name.replace(' ', '-')
    resource_name = re.sub(r'[^a-z0-9\-]', '', resource_name)  # Remove invalid characters
    return resource_name.strip()

# Function to perform the Kubernetes action
def perform_kubernetes_action(action):
    try:
        if action.get("action") == "unknown" or not action.get("parameters"):
            user_query = action.get("query", "Unknown query")
            logger.info("Action or parameters not recognized, delegating to handle_unknown_action.")
            return handle_unknown_action({"query": user_query})

        action_type = normalize_action_type(action.get("action"))
        parameters = action.get("parameters", {})

        # Normalize 'resource_type' in parameters
        if 'resource_type' in parameters:
            parameters['resource_type'] = normalize_resource_type(parameters['resource_type'])

        # Normalize 'resource_name' in parameters
        if 'resource_name' in parameters:
            parameters['resource_name'] = normalize_resource_name(parameters['resource_name'])

        # Map action types to handler functions
        action_handlers = {
            "count_resources": handle_count_resources,
            "get_status": handle_get_status,
            "list_resources": handle_list_resources,
            "get_logs": handle_get_logs,
            "describe_resource": handle_describe_resource,
            "get_resource_detail": handle_get_resource_detail,
            "unknown": handle_unknown_action,
        }

        handler = action_handlers.get(action_type)
        if not handler:
            logger.error(f"Unknown action type after normalization: {action_type}")
            return "I did not understand the action required."

        # Call the handler function
        answer = handler(parameters)
        return answer

    except client.exceptions.ApiException as e:
        logger.error(f"Kubernetes API exception: {e}")
        return "An error occurred while communicating with the Kubernetes API."

    except Exception as e:
        logger.error(f"Error performing Kubernetes action: {e}")
        return "An error occurred while performing the Kubernetes action."

# Handler functions for different actions
def handle_count_resources(params):
    resource_type = params.get("resource_type")

    if resource_type == "pod":
        pods = core_v1_api.list_pod_for_all_namespaces()
        count = len(pods.items)
    elif resource_type == "deployment":
        deployments = apps_v1_api.list_deployment_for_all_namespaces()
        count = len(deployments.items)
    elif resource_type == "node":
        nodes = core_v1_api.list_node()
        count = len(nodes.items)
    elif resource_type == "service":
        services = core_v1_api.list_service_for_all_namespaces()
        count = len(services.items)
    else:
        return f"Resource type '{resource_type}' is not supported for counting."

    return str(count)

def handle_get_status(params):
    resource_type = params.get("resource_type")
    resource_name = params.get("resource_name")

    if resource_type == "pod":
        pod, namespace = find_resource_in_all_namespaces(core_v1_api.read_namespaced_pod, resource_name)
        if pod:
            status = pod.status.phase
            return f"The status of pod '{resource_name}' in namespace '{namespace}' is '{status}'."
        else:
            return f"Pod '{resource_name}' not found in any namespace."
    elif resource_type == "deployment":
        deployment, namespace = find_resource_in_all_namespaces(apps_v1_api.read_namespaced_deployment, resource_name)
        if deployment:
            conditions = deployment.status.conditions
            status = conditions[-1].type if conditions else "Unknown"
            return f"The status of deployment '{resource_name}' in namespace '{namespace}' is '{status}'."
        else:
            return f"Deployment '{resource_name}' not found in any namespace."
    elif resource_type == "service":
        logger.info('control came in resource_type service')
        service, namespace = find_resource_in_all_namespaces(core_v1_api.read_namespaced_service, resource_name)

        if service:
            status = service.spec.type
            return f"The status of service '{resource_name}' in namespace '{namespace}' is '{status}'."
        else:
            return f"Service '{resource_name}' not found in any namespace."
    else:
        return f"Resource type '{resource_type}' is not supported for status retrieval."

def handle_list_resources(params):
    resource_type = params.get("resource_type")
    namespace = params.get("namespace")

    if resource_type == "pod":
        if namespace:
            pods = core_v1_api.list_namespaced_pod(namespace=namespace)
        else:
            pods = core_v1_api.list_pod_for_all_namespaces()
        resource_names = [simplify_name(pod.metadata.name) for pod in pods.items]
    elif resource_type == "deployment":
        if namespace:
            deployments = apps_v1_api.list_namespaced_deployment(namespace=namespace)
        else:
            deployments = apps_v1_api.list_deployment_for_all_namespaces()
        resource_names = [simplify_name(dep.metadata.name) for dep in deployments.items]
    elif resource_type == "service":
        if namespace:
            services = core_v1_api.list_namespaced_service(namespace=namespace)
        else:
            services = core_v1_api.list_service_for_all_namespaces()
        resource_names = [simplify_name(svc.metadata.name) for svc in services.items]
    elif resource_type == "namespace":
        namespaces = core_v1_api.list_namespace()
        resource_names = [ns.metadata.name for ns in namespaces.items]
    else:
        return f"Resource type '{resource_type}' is not supported for listing."

    return ", ".join(resource_names)

def handle_get_logs(params):
    pod_name = params.get("resource_name")

    if not pod_name:
        return "Pod name is required to get logs."

    pod, namespace = find_resource_in_all_namespaces(core_v1_api.read_namespaced_pod, pod_name)
    if not pod:
        return f"Pod '{pod_name}' not found in any namespace."

    logs = core_v1_api.read_namespaced_pod_log(name=pod_name, namespace=namespace)
    return logs

def handle_describe_resource(params):
    resource_type = params.get("resource_type")
    resource_name = params.get("resource_name")

    if resource_type == "pod":
        pod, namespace = find_resource_in_all_namespaces(core_v1_api.read_namespaced_pod, resource_name)
        if pod:
            return yaml.safe_dump(pod.to_dict())
        else:
            return f"Pod '{resource_name}' not found in any namespace."
    elif resource_type == "deployment":
        deployment, namespace = find_resource_in_all_namespaces(apps_v1_api.read_namespaced_deployment, resource_name)
        if deployment:
            return yaml.safe_dump(deployment.to_dict())
        else:
            return f"Deployment '{resource_name}' not found in any namespace."
    elif resource_type == "service":
        service, namespace = find_resource_in_all_namespaces(core_v1_api.read_namespaced_service, resource_name)
        if service:
            return yaml.safe_dump(service.to_dict())
        else:
            return f"Service '{resource_name}' not found in any namespace."
    else:
        return f"Description not supported for resource type '{resource_type}'."

def handle_get_resource_detail(params):
    resource_type = params.get("resource_type")
    resource_name = params.get("resource_name")
    detail = params.get("detail")
    variable_name = params.get("variable_name") or params.get("specific_detail")
    namespace = params.get("namespace")

    if not resource_name or not detail:
        return "Resource name and detail are required for getting resource details."

    try:
        if resource_type == "pod":
            pod, namespace = find_resource_in_all_namespaces(core_v1_api.read_namespaced_pod, resource_name)
            if not pod:
                return f"Pod '{resource_name}' not found in any namespace."
            if detail == "environment_variable" and variable_name:
                env_vars = pod.spec.containers[0].env or []
                for env in env_vars:
                    if env.name == variable_name:
                        return f"The value of the environment variable '{variable_name}' is '{env.value}'."
                return f"Environment variable '{variable_name}' not found in pod '{resource_name}'."
            elif detail == "mount_path":
                volume_mounts = pod.spec.containers[0].volume_mounts or []
                mount_paths = [vm.mount_path for vm in volume_mounts]
                return f"Mount paths for pod '{resource_name}': {', '.join(mount_paths)}"
            elif detail == "readiness_probe_path":
                readiness_probe = pod.spec.containers[0].readiness_probe
                if readiness_probe and readiness_probe.http_get:
                    path = readiness_probe.http_get.path
                    return f"The readiness probe path for pod '{resource_name}' is '{path}'."
                else:
                    return f"No readiness probe path found for pod '{resource_name}'."
            elif detail == "container_port":
                ports = pod.spec.containers[0].ports or []
                port_numbers = [str(port.container_port) for port in ports]
                return f"Container ports for pod '{resource_name}': {', '.join(port_numbers)}"
            else:
                return f"Detail '{detail}' is not supported for resource type '{resource_type}'."
        elif resource_type == "deployment":
            deployment, namespace = find_resource_in_all_namespaces(apps_v1_api.read_namespaced_deployment, resource_name)
            if not deployment:
                return f"Deployment '{resource_name}' not found in any namespace."
            if detail == "environment_variable" and variable_name:
                env_vars = deployment.spec.template.spec.containers[0].env or []
                for env in env_vars:
                    if env.name == variable_name:
                        return f"The value of the environment variable '{variable_name}' is '{env.value}'."
                return f"Environment variable '{variable_name}' not found in deployment '{resource_name}'."
            elif detail == "mount_path":
                volume_mounts = deployment.spec.template.spec.containers[0].volume_mounts or []
                mount_paths = [vm.mount_path for vm in volume_mounts]
                return f"Mount paths for deployment '{resource_name}': {', '.join(mount_paths)}"
            else:
                return f"Detail '{detail}' is not supported for resource type '{resource_type}'."
        elif resource_type == "service":
            logger.info('Service came here insideget resource detail')
            service, namespace = find_resource_in_all_namespaces(core_v1_api.read_namespaced_service, resource_name)
            logger.info(f"Fetched Service:{service} and namespace {namespace}")
            if not service:
                return f"Service '{resource_name}' not found in any namespace."
            if detail == "port":
                ports = service.spec.ports or []
                port_numbers = [str(port.port) for port in ports]
                return f"Ports for service '{resource_name}': {', '.join(port_numbers)}"
            elif detail == "namespace":
                return f"The service '{resource_name}' is deployed in the '{namespace}' namespace."
            else:
                return f"Detail '{detail}' is not supported for resource type '{resource_type}'."
        elif resource_type == "persistentvolume":
            pv = core_v1_api.read_persistent_volume(name=resource_name)
            if detail == "mount_path":
                # PersistentVolumes do not have mount paths; mount paths are defined in pods or deployments.
                return f"PersistentVolume '{resource_name}' details: {pv.spec}"
            else:
                return f"Detail '{detail}' is not supported for resource type '{resource_type}'."
        else:
            return f"Resource type '{resource_type}' is not supported for getting resource details."
    except client.exceptions.ApiException as e:
        logger.error(f"Kubernetes API exception: {e}")
        return f"An error occurred while retrieving details: {e.reason}"

def handle_unknown_action(params):
    user_query = params.get("query", "Unknown query")  # Use the original query for context if available
    # Define a prompt to query the LLM for Kubernetes API suggestions
    prompt = (
        f"You are an assistant with knowledge of Kubernetes Python client commands. "
        f"The user has requested an unknown action: '{user_query}'. "
        f"Using the Kubernetes client objects 'core_v1_api' and 'apps_v1_api', "
        f"suggest a Python code snippet that would fulfill this request. "
        f"Assign the result to a variable 'result'. "
        f"Respond only with the suggested Python code without additional text."
    )

    # Query the LLM for command suggestions
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a Kubernetes assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=150
        )

        # Extract the suggested command from LLM response
        suggested_command = response.choices[0].message.content.strip()
        logger.info(f"LLM suggested command: {suggested_command}")

        # Execute the suggested command safely
        result = eval_suggested_command(suggested_command)

        # Return the result in the required format
        return format_response(result)

    except Exception as e:
        logger.error(f"Error querying the LLM or executing suggested command: {e}")
        return "The requested action could not be performed. Please check the query or try again."

def eval_suggested_command(suggested_command):
    try:
        # Execute the suggested command and return its result
        # Using exec in a controlled environment to avoid executing harmful code
        local_vars = {"core_v1_api": core_v1_api, "apps_v1_api": apps_v1_api}
        exec(suggested_command, {"__builtins__": {}}, local_vars)
        result = local_vars.get('result', 'Command executed.')
        return result
    except Exception as e:
        logger.error(f"Error executing suggested command: {e}")
        return "The command could not be executed."

def format_response(result):
    if isinstance(result, str):
        return result
    elif hasattr(result, "items"):  # For lists of items like pods, deployments, etc.
        resource_names = [simplify_name(item.metadata.name) for item in result.items]
        return ", ".join(resource_names)
    else:
        return str(result)

# Helper function to simplify resource names
def simplify_name(name):
    simplified_name = re.sub(r'-[a-z0-9]{9,}$', '', name)
    return simplified_name

# Helper function to find resource across all namespaces
def find_resource_in_all_namespaces(api_method, resource_name):
    namespaces = core_v1_api.list_namespace()
    logger.info(f"List all namespaces: {namespaces}")
    for ns in namespaces.items:
        namespace = ns.metadata.name
        try:
            resource = api_method(name=resource_name, namespace=namespace)
            logger.info(f"Resource fetched : {resource} from resource_name: {resource_name} and namespace : {namespace}")
            return resource, namespace
        except client.exceptions.ApiException as e:
            if e.status != 404:
                logger.error(f"Error accessing resource '{resource_name}' in namespace '{namespace}': {e}")
                continue
    return None, None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
