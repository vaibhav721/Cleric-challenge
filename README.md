# Cleric Query Agent Assignment

## Introduction

This project is developed as part of the Cleric home assignment. The objective is to create an AI-powered query agent that interacts with a Kubernetes cluster to retrieve information such as status, logs, and other details about resources deployed on Minikube. The agent leverages OpenAI's GPT-4 model to interpret natural language queries and executes corresponding Kubernetes client commands to fetch the requested information.

## Approach

The application is built using Python and Flask, integrating the Kubernetes Python client and OpenAI's GPT-4 model. The key components and steps in the approach are:

1. **Natural Language Understanding**: The agent uses GPT-4 to interpret user queries and extract the intended action and parameters.

2. **Action Normalization**: To handle variations in user input, the application normalizes action types and resource types to a standard format that the backend can process.

3. **Dynamic Command Execution**: If the user's query doesn't match predefined actions, the agent queries GPT-4 to generate appropriate Kubernetes client commands, which are then safely executed.

4. **Robust Error Handling**: The application includes comprehensive error handling to manage exceptions, API errors, and unsupported queries gracefully.

5. **Security Considerations**: Care is taken to execute dynamically generated code securely, using controlled environments and limiting the scope of execution to prevent unauthorized actions.

## Features

- Interpret and execute queries related to counting resources, getting statuses, listing resources, retrieving logs, and describing resources.
- Handle unknown or unsupported queries by leveraging GPT-4 to generate and execute appropriate Kubernetes client commands.
- Normalize user input to handle synonyms, abbreviations, and plural forms.
- Provide concise and accurate responses without extraneous identifiers.
- Support for read-only operations on a Minikube Kubernetes cluster.

## Scope and Limitations

- **Supported Queries**: The agent focuses on read-only actions such as retrieving status, information, or logs of resources deployed on Minikube.
- **Number of Queries**: Approximately 10 queries are expected to be handled independently.
- **Dynamic Responses**: Answers are based on the current state of the cluster but do not change dynamically within a single interaction.
- **Resource Names**: Responses exclude generated suffixes or identifiers, returning simplified resource names (e.g., "mongodb" instead of "mongodb-56c598c8fc").

## Environment Setup

Follow the steps below to set up the environment and run the application.

### Prerequisites

- **Python 3.7 or higher**
- **pip** (Python package installer)
- **Minikube** installed and configured
- **kubectl** command-line tool installed
- **OpenAI API Key**

### Installation Steps

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/cleric-query-agent.git
   cd cleric-query-agent
