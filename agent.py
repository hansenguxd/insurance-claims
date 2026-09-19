import os
import json
from dotenv import load_dotenv

# Add references
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FunctionTool
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import PromptAgentDefinition, FunctionTool
from openai.types.responses.response_input_param import FunctionCallOutput, ResponseInputParam
from functions_auto_claim import auto_claim_query, auto_claim_detail_query, auto_claim_risk_check

# Safety cap on how many tool-call rounds the model may chain in a single user turn
# (e.g. auto_claim_query -> auto_claim_detail_query -> ...).
MAX_TOOL_ROUNDS = 10

def main(): 
    # Clear the console
    os.system('cls' if os.name=='nt' else 'clear')

    # Load environment variables from .env file
    load_dotenv()
    project_endpoint = os.getenv("PROJECT_ENDPOINT")
    model_deployment = os.getenv("MODEL_DEPLOYMENT_NAME")

   
    # Force TLS to use the corporate CA bundle. Python's default certifi bundle
    # does NOT include the private CA your network proxy uses to intercept TLS,
    # which causes: SSL: CERTIFICATE_VERIFY_FAILED - unable to get local issuer
    # Fix : Set the REQUESTS_CA_BUNDLE and SSL_CERT_FILE env vars inside the script to point at the corporate bundle at %USERPROFILE%\.az-certs\combined-ca-bundle.pem (overridable via a CA_BUNDLE env var).
    ca_bundle = os.environ.get(
        "CA_BUNDLE",
        os.path.join(os.path.expanduser("~"), ".az-certs", "combined-ca-bundle.pem"),
    )
    if os.path.isfile(ca_bundle):
        os.environ["REQUESTS_CA_BUNDLE"] = ca_bundle
        os.environ["SSL_CERT_FILE"] = ca_bundle

  
    # Connect to the project client
    with (
       DefaultAzureCredential() as credential,
       AIProjectClient(endpoint=project_endpoint, credential=credential) as project_client,
       project_client.get_openai_client() as openai_client,
    ):

        # Define the event function tool (local data)
 
        # Define the SQL event function tool (database)

        # Define the auto-claim query function tool (Azure SQL Server)
        auto_claim_tool = FunctionTool(
            name="auto_claim_query",
            description="Query the auto-claim Azure SQL database for customers whose total claim amount exceeds the given threshold. IMPORTANT: pass the EXACT amount the user mentions as 'threshold' (e.g. user says 'greater than 20000' → threshold=20000). Only use 10000 when the user does not specify any amount. Returns the CustomerID, FirstName, LastName and TotalClaimAmount.",
            parameters={
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "description": "the EXACT claim amount threshold the user mentioned. Only customers with total claims GREATER than this value are returned (e.g. 'over 20000' → 20000). Use 10000 only when the user specifies no amount.",
                    },
                },
                "required": ["threshold"],
                "additionalProperties": False,
            },
            strict=True,
        )

        # Define the auto-claim detail function tool (Azure SQL Server)
        auto_claim_detail_tool = FunctionTool(
            name="auto_claim_detail_query",
            description="Query the auto-claim Azure SQL database for the full policy/claim detail of specific customers. Takes the list of CustomerIDs (e.g. the ones returned by auto_claim_query) and returns PolicyNumber, VehicleMake, VehicleModel, ClaimNumber, ClaimStatus and ClaimAmount per row. Use after auto_claim_query to see the granular policy and claim details for the high-value customers, or when the user asks for the policy/claim detail of specific customer IDs.",
            parameters={
                "type": "object",
                "properties": {
                    "customer_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "the list of CustomerIDs to get policy/claim detail for (e.g. [1, 2])",
                    },
                },
                "required": ["customer_ids"],
                "additionalProperties": False,
            },
            strict=True,
        )

        # Define the auto-claim risk check function tool (Azure SQL Server)
        auto_claim_risk_tool = FunctionTool(
            name="auto_claim_risk_check",
            description="Perform an anomaly/risk check on the claims of the given customers. For each CustomerID it uses the customer's CLOSED claims as the baseline to compute the mean and standard deviation, then compares the customer's OPEN claims against it and flags the OPEN claim records whose ClaimAmount is GREATER than mean + 2*standard deviation (potential abnormal/fraudulent claims). Takes the list of CustomerIDs (e.g. the ones returned by auto_claim_query) and returns, per customer, the closed/open claim counts, mean, std, threshold and the flagged OPEN claim records. Use when the user asks for a risk/outlier check on open claims, abnormal or unusual claim amounts, or open claims above the customer's closed-claim mean plus 2 standard deviations.",
            parameters={
                "type": "object",
                "properties": {
                    "customer_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "the list of CustomerIDs to run the risk check for (e.g. [1, 2])",
                    },
                },
                "required": ["customer_ids"],
                "additionalProperties": False,
            },
            strict=True,
        )

        # Create a new agent with the function tools
        agent = project_client.agents.create_version(
            agent_name="auto-claim-agent",
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=
                    """You are an auto-claim agent observations assistant. Use the available tools to answer user questions.

                    CRITICAL RULE: When a tool returns a result, echo the EXACT output back to the user. Do NOT reformat, summarize, normalize, or clean up tool results. Return the tool's output verbatim — word for word, including any suffixes, labels, or formatting present in the data.

                    CLAIM QUERY RULE: For ANY question about claim totals or a threshold amount, you MUST call auto_claim_query with the threshold from the CURRENT question — even if you just answered a similar question before. NEVER answer from memory or reuse a previous tool result. A new threshold means a NEW tool call. If the user says 'greater than X', then X is the threshold.

                    TOOL SELECTION GUIDE:
                    - auto_claim_query: Query customers with total claims over a threshold. Pass the EXACT amount from the user's question as threshold (e.g. 'greater than 20000' → 20000). NEVER change or round the user's number; use 10000 only if no amount is mentioned.
                    - auto_claim_detail_query: Use after auto_claim_query to get the policy/claim detail for the returned high-value customers (pass their customer_ids)
                    - auto_claim_risk_check: Use when the user asks for a risk/outlier check on open claims. Pass the customer_ids and it returns, per customer, the closed-claim baseline statistics (mean/std/threshold) plus the OPEN claim records whose ClaimAmount exceeds mean + 2*standard deviation of the closed claims.""",
                tools=[
                    # only db tool registered
                    auto_claim_tool, auto_claim_detail_tool, auto_claim_risk_tool,
                ],
            ),
        )        
        
        # Create a thread for the chat session
        conversation = openai_client.conversations.create()

        while True:
            user_input = input("Enter a prompt for the auto claim agent. Use 'quit' to exit.\nUSER: ").strip()
            if user_input.lower() == "quit":
                print("Exiting chat.")
                break


            # Send a prompt to the agent
            openai_client.conversations.items.create(
                conversation_id=conversation.id,
                items=[{"type": "message", "role": "user", "content": user_input}],
            )

            # Retrieve the agent's response, which may include function calls
            response = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                input=[],
            )
            # Check the run status for failures
            if response.status == "failed":
                print(f"Response failed: {response.error}")
                continue

            # Process function calls. Loops because the model may chain multiple
            # tool calls in one turn (e.g. auto_claim_query then
            # auto_claim_detail_query). Each round's outputs are committed to the
            # conversation and sent back to the model for the final answer.
            tool_round = 0
            while any(item.type == "function_call" for item in response.output):
                tool_round += 1
                if tool_round > MAX_TOOL_ROUNDS:
                    print(f"Reached the maximum number of tool-call rounds ({MAX_TOOL_ROUNDS}); stopping.")
                    break

                tool_outputs: ResponseInputParam = []
                for item in response.output:
                    if item.type != "function_call":
                        continue
                    # Retrieve the matching function tool
                    function_name = item.name
                    args = json.loads(item.arguments)
                    print(f"[DEBUG] {function_name} arguments: {args}")
                    result = None
                    if function_name == "auto_claim_query":
                        result = json.dumps(auto_claim_query(**args))
                    elif function_name == "auto_claim_detail_query":
                        result = json.dumps(auto_claim_detail_query(**args))
                    elif function_name == "auto_claim_risk_check":
                        result = json.dumps(auto_claim_risk_check(**args))

                    # Append the output text
                    tool_outputs.append(
                        FunctionCallOutput(
                            type="function_call_output",
                            call_id=item.call_id,
                            output=result,
                        )
                    )

                # Send function call outputs back to the model and retrieve a response
                response = openai_client.responses.create(
                    conversation=conversation.id,
                    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
                    input=tool_outputs,
                )
                if response.status == "failed":
                    print(f"Response failed: {response.error}")
                    break

            # Display the agent's response
            print(f"AGENT: {response.output_text}")
            

        # Delete the agent when done
        project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
        print("Deleted agent.")        

if __name__ == '__main__': 
    main()