import os
import sys
import logging
import requests
import weaviate
from weaviate.classes.init import Auth
from weaviate.agents.query import QueryAgent
from weaviate_agents.classes import QueryAgentCollectionConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def set_output(name, value):
    """Set GitHub Action output if running in GitHub Actions"""
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"{name}={value}\n")


# Validate required environment variables
required_env_vars = ["WEAVIATE_URL", "GITHUB_TOKEN", "ISSUE_BODY", "ISSUE_NUMBER"]

missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
if missing_vars:
    error_msg = f"Missing required environment variables: {missing_vars}"
    logger.error(error_msg)
    set_output("found_similar_issue", "false")
    set_output("comment_posted", "false")
    set_output("error_message", error_msg)
    sys.exit(1)

weaviate_url = os.environ["WEAVIATE_URL"]
weaviate_api_key = os.environ["WEAVIATE_API_KEY"]
github_token = os.environ["GITHUB_TOKEN"]
issue_body = os.environ["ISSUE_BODY"]
issue_number = os.environ["ISSUE_NUMBER"]
collection_name = os.environ.get("COLLECTION_NAME", "GitHubIssues")

# Use the GITHUB_REPO_NAME input if provided, otherwise fall back to the GitHub Actions default env
repo_full_name = os.environ.get("GITHUB_REPO_NAME")
if not repo_full_name:
    repo_full_name = os.environ.get("GITHUB_REPOSITORY", "")

if not repo_full_name:
    error_msg = (
        "Repository full name is not set. Please specify github_repository input."
    )
    logger.error(error_msg)
    set_output("found_similar_issue", "false")
    set_output("comment_posted", "false")
    set_output("error_message", error_msg)
    sys.exit(1)

# Validate issue number is numeric
try:
    int(issue_number)
except ValueError:
    error_msg = f"Invalid issue number: {issue_number}"
    logger.error(error_msg)
    set_output("found_similar_issue", "false")
    set_output("comment_posted", "false")
    set_output("error_message", error_msg)
    sys.exit(1)


def convert_to_italic(text: str) -> str:
    """
    Wraps each paragraph in underscores for GitHub Markdown italics.
    Handles multiple paragraphs by wrapping each separately.
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return "\n\n".join(f"_{p}_" for p in paragraphs)


try:
    client = weaviate.connect_to_weaviate_cloud(
        cluster_url=weaviate_url,
        auth_credentials=Auth.api_key(weaviate_api_key),
    )
    logger.info("Successfully connected to Weaviate")
except Exception as e:
    error_msg = f"Failed to connect to Weaviate: {e}"
    logger.error(error_msg)
    set_output("found_similar_issue", "false")
    set_output("comment_posted", "false")
    set_output("error_message", error_msg)
    sys.exit(1)

no_match_phrase = "No GitHub issue contains an exact or very close body description"

system_prompt = (
    "GOAL:\n"
    "Your goal is to identify the single most relevant and semantically similar issue from a vectorized database of GitHub issues.\n\n"
    "CONTEXT:\n"
    "- The database contains issues with fields: title, body, comments, URL, number, state, labels, author, and repository.\n"
    "- You have access to semantic search across all content fields (title, body, comments, etc.).\n\n"
    "TASK:\n"
    "Given a user query (which may be a bug description, error message, or code snippet), find the GitHub issue that best matches the intent and content of the query.\n"
    "OUTPUT FORMAT:\n"
    "- If no similar or very close issue exists, you MUST return EXACTLY this phrase and nothing else:\n"
    "'{no_match_phrase}'\n\n"
    "If a similar issue IS found, respond in this GitHub Markdown format:\n"
    "- [Issue owner/repo#Number: Issue title](URL)\n"
    "A brief explanation of the issue, one or two sentences.\n\n"
    "If the issue is closed, add '(Closed)' after the title and state why in the explanation.\n\n"
    "EXAMPLES:\n"
    "- [Issue weaviate/weaviate#6549: Collection name does not always auto capitalize the first letter](https://github.com/weaviate/weaviate/issues/6549)\n"
    "This issue describes the inconsistent auto-capitalization of collection names in Weaviate. (Closed as fixed.)\n\n"
    "- [Issue weaviate/weaviate#5789: Case sensitivity in collection names](https://github.com/weaviate/weaviate/issues/5789)\n"
    "This open issue discusses broader case sensitivity inconsistencies in collection names.\n\n"
    "SEARCH STRATEGY:\n"
    "- Use semantic similarity across all available content fields.\n"
    "- Consider both technical and contextual relevance.\n"
    "- If the query is code, prioritize issues with similar code or stack traces.\n"
    "- If a panic error is provided, prioritize issues with similar error messages.\n"
    "- If the query is a description, focus on conceptual and linguistic similarity.\n\n"
    "IMPORTANT: Do NOT add any greeting, summary, or extra explanation. Only output the Markdown bullet and explanation as shown above, OR the exact no-match phrase."
)

try:
    agent = QueryAgent(
        client=client,
        collections=[
            QueryAgentCollectionConfig(
                name=collection_name,
                target_vector=["all_content"],
                view_properties=["title", "body", "comments", "url", "number", "state", "createdAt", "updatedAt", "closedAt", "labels", "author", "repository"]
            ),
        ],
        system_prompt=system_prompt,
    )
    logger.info(f"QueryAgent initialized with collection: {collection_name}")
except Exception as e:
    error_msg = f"Failed to initialize QueryAgent: {e}"
    logger.error(error_msg)
    client.close()
    set_output("found_similar_issue", "false")
    set_output("comment_posted", "false")
    set_output("error_message", error_msg)
    sys.exit(1)

query = f"Find the most similar GitHub issue (if any) to this issue body: '{issue_body}'\n\nIf no similar issue exists, return exactly: '{no_match_phrase}'"

try:
    result = agent.run(query)
    result_text = result.final_answer
    logger.info("Query executed successfully")
except Exception as e:
    error_msg = f"Failed to execute query: {e}"
    logger.error(error_msg)
    client.close()
    set_output("found_similar_issue", "false")
    set_output("comment_posted", "false")
    set_output("error_message", error_msg)
    sys.exit(1)

result.display()

# Only comment if the result does NOT contain the specific phrase indicating no match
if "no github issue" in result_text.lower():
    logger.info("No relevant issue found, skipping comment.")
    set_output("found_similar_issue", "false")
    set_output("comment_posted", "false")
    set_output("error_message", "")
    client.close()
    sys.exit(0)

# Similar issue found
set_output("found_similar_issue", "true")

comment_body = (
    f"👋 Thanks for opening this issue!\n\n"
    f"I found a similar issue in our tracker that might address your problem:\n\n"
    f"{convert_to_italic(result_text)}\n\n"
    f"Please check if this is the same issue. If so, consider adding your input there or closing this one. Thanks for helping us keep the issue tracker organized! 🚀"
)

comments_url = (
    f"https://api.github.com/repos/{repo_full_name}/issues/{issue_number}/comments"
)
headers = {
    "Authorization": f"Bearer {github_token}",
    "Accept": "application/vnd.github+json",
}

try:
    response = requests.post(comments_url, json={"body": comment_body}, headers=headers)
    if response.status_code == 201:
        logger.info("Comment posted successfully.")
        set_output("comment_posted", "true")
        set_output("error_message", "")
        client.close()
        sys.exit(0)
    else:
        error_msg = f"Failed to post comment: {response.status_code} {response.text}"
        logger.error(error_msg)
        set_output("comment_posted", "false")
        set_output("error_message", error_msg)
        client.close()
        sys.exit(1)
except Exception as e:
    error_msg = f"Exception while posting comment: {e}"
    logger.error(error_msg)
    set_output("comment_posted", "false")
    set_output("error_message", error_msg)
    client.close()
    sys.exit(1)
