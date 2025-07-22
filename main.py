import os
import requests
import weaviate
from weaviate.classes.init import Auth
from weaviate.agents.query import QueryAgent
from weaviate_agents.classes import QueryAgentCollectionConfig

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
    print(
        "Error: Repository full name is not set. Please specify github_repository input."
    )
    exit(1)


def convert_to_italic(text: str) -> str:
    """
    Wraps each paragraph in underscores for GitHub Markdown italics.
    Handles multiple paragraphs by wrapping each separately.
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return "\n\n".join(f"_{p}_" for p in paragraphs)


client = weaviate.connect_to_weaviate_cloud(
    cluster_url=weaviate_url,
    auth_credentials=Auth.api_key(weaviate_api_key),
)

no_match_phrase = "No GitHub issue contains an exact or very close body description"

# old_system_prompt = (
#     "You are an expert assistant for matching GitHub issues to user-provided descriptions, sentences, or code snippets. "
#     "Your goal is to identify the single most relevant and semantically similar issue from a vectorized database of GitHub issues.\n\n"
#     "CONTEXT:\n"
#     "- The database contains issues with fields: title, body, URL, number, state, labels, author, and repository.\n"
#     "- You have access to semantic search across all content fields (title, body, comments, etc.).\n\n"
#     "TASK:\n"
#     "Given a user query (which may be a bug description, error message, or code snippet), find the GitHub issue that best matches the intent and content of the query.\n"
#     "Return only the single best-matching issue, unless there is a clear tie.\n\n"
#     "SEARCH STRATEGY:\n"
#     "- Use semantic similarity across all available content fields.\n"
#     "- Consider both technical and contextual relevance.\n"
#     "- If the query is code, prioritize issues with similar code or stack traces.\n"
#     "- If the query is a description, focus on conceptual and linguistic similarity.\n\n"
#     "OUTPUT FORMAT:\n"
#     "Respond in valid GitHub Markdown:\n"
#     "- A single bullet with a clickable link to the issue, [Issue owner/repo#Number: Issue title]. For example: [Issue weaviate/weaviate#1234: Title])\n"
#     "- A brief explanation in italics below the link.\n"
#     "- If the issue is closed, state that it is closed and why.\n"
#     "- Do not include the input query in the response to keep the response short.\n"
#     "If there is no answer do not cite sources. \n\n"
#     "Be concise and precise. Do not include unrelated issues or extraneous information."
# )
system_prompt = (
    "Respond ONLY in the following GitHub Markdown format. Do NOT add any other text, greeting, or explanation. "
    "Do NOT include the input query, unrelated issues, or any other text. "
    "- [Issue owner/repo#Number: Issue title](URL)\n"
    "A brief explanation of the issue, one or two sentences.\n\n"
    "If the issue is closed, add '(Closed)' after the title and state why in the explanation.\n\n"
    "EXAMPLES (do exactly this):\n"
    "- [Issue weaviate/weaviate#6549: Collection name does not always auto capitalize the first letter](https://github.com/weaviate/weaviate/issues/6549)\n"
    "This issue describes the inconsistent auto-capitalization of collection names in Weaviate. (Closed as fixed.)\n\n"
    "- [Issue weaviate/weaviate#5789: Case sensitivity in collection names](https://github.com/weaviate/weaviate/issues/5789)\n"
    "This open issue discusses broader case sensitivity inconsistencies in collection names.\n\n"
    "BAD EXAMPLE (do NOT do this):\n"
    "There is an existing GitHub issue that directly relates to the described problem about Weaviate automatically capitalizing the first letter of collection names to follow GraphQL conventions, but this behavior being inconsistent across contexts. The issue is titled ...\n\n"
    "Do NOT add any greeting, summary, or extra explanation. Only output the Markdown bullet and explanation as shown above."
    "You are an expert assistant for matching GitHub issues to user-provided descriptions, sentences, or code snippets. "
    "GOAL:\n"
    "Your goal is to identify the single most relevant and semantically similar issue from a vectorized database of GitHub issues.\n\n"
    "CONTEXT:\n"
    "- The database contains issues with fields: title, body, URL, number, state, labels, author, and repository.\n"
    "- You have access to semantic search across all content fields (title, body, comments, etc.).\n\n"
    "TASK:\n"
    "Given a user query (which may be a bug description, error message, or code snippet), find the GitHub issue that best matches the intent and content of the query.\n"
    "Return only the single best-matching issue, unless there is a clear tie.\n\n"
    "SEARCH STRATEGY:\n"
    "- Use semantic similarity across all available content fields.\n"
    "- Consider both technical and contextual relevance.\n"
    "- If the query is code, prioritize issues with similar code or stack traces.\n"
    "- If the query is a description, focus on conceptual and linguistic similarity.\n\n"
)

agent = QueryAgent(
    client=client,
    collections=[
        QueryAgentCollectionConfig(
            name=collection_name,
            target_vector=["all_content"],
        ),
    ],
    system_prompt=system_prompt,
)

query = f"Check if there are any existing GitHub issues related to the following github issue body: \n\n '{issue_body}'\n\n If no similar issue exists, return the following phrase (literally): '{no_match_phrase}'."
result = agent.run(query)

result_text = result.final_answer

result.display()

# Only comment if the result does NOT contain the specific phrase indicating no match
if no_match_phrase in result_text:
    print("No relevant issue found, skipping comment.")
    client.close()
    exit(0)

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
response = requests.post(comments_url, json={"body": comment_body}, headers=headers)
if response.status_code == 201:
    print("Comment posted successfully.")
else:
    print(f"Failed to post comment: {response.status_code} {response.text}")

client.close()
