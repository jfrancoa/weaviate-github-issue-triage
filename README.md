# weaviate-github-issue-triage

GitHub Action to detect duplicate issues and assist in triaging new ones efficiently by leveraging Weaviate's semantic search.

## Prerequisite: Vectorize Your Issues

Before using this action, you must first vectorize all your GitHub issues into your Weaviate instance. Use the [weaviate/github-issues-to-weaviate](https://github.com/weaviate/github-issues-to-weaviate) GitHub Action to do this. This action fetches all issues from your repository and stores them as vectors in Weaviate, enabling semantic search for triage.

---

## Usage

Add this action to your workflow to automatically check new GitHub issues for semantic similarity against a Weaviate instance. If a similar issue is found, the action will comment on the issue with a link and explanation.

### Example Workflow

```yaml
name: Issue Similarity Triage

on:
  issues:
    types: [opened]

jobs:
  triage:
    runs-on: ubuntu-latest
    steps:
      - name: Check for similar issues
        id: similarity-check
        uses: weaviate/weaviate-github-issue-triage@v1
        with:
          issue_body: ${{ github.event.issue.body }}
          issue_number: ${{ github.event.issue.number }}
          weaviate_url: ${{ secrets.WEAVIATE_URL }}
          weaviate_api_key: ${{ secrets.WEAVIATE_API_KEY }} # optional
          github_token: ${{ secrets.GITHUB_TOKEN }}
          collection_name: GitHubIssues  # optional
          github_repository: ${{ github.repository }}  # optional

      - name: Log results
        if: always()
        run: |
          echo "Found similar issue: ${{ steps.similarity-check.outputs.found_similar_issue }}"
          echo "Comment posted: ${{ steps.similarity-check.outputs.comment_posted }}"
          if [ "${{ steps.similarity-check.outputs.error_message }}" != "" ]; then
            echo "Error: ${{ steps.similarity-check.outputs.error_message }}"
          fi
```

## Inputs

| Name               | Required | Description                                                                                       | Default         |
|--------------------|----------|---------------------------------------------------------------------------------------------------|-----------------|
| `issue_body`       | Yes      | The body content of the newly opened GitHub issue. Used as the query for semantic similarity.     | —               |
| `issue_number`     | Yes      | The number of the newly opened GitHub issue. Used to post comments if a duplicate is found.       | —               |
| `weaviate_url`     | Yes      | The URL of your Weaviate instance.                                                                | —               |
| `weaviate_api_key` | No      | API key for authenticating with your Weaviate instance. If not authentication is configured you can use the default or pass empty string.                                         | —               |
| `github_token`     | Yes      | GitHub token with permission to post comments on issues. Usually `${{ secrets.GITHUB_TOKEN }}`.   | —               |
| `collection_name`  | No       | Name of the Weaviate collection to search for similar issues.                                     | `GitHubIssues`  |
| `github_repository`| No       | Repository in `owner/repo` format. If not set, defaults to the current repository context.        | —               |

### Parameter Explanations

- **issue_body**: The content/body of the issue that was just opened. This is used as the query for semantic similarity search in Weaviate.
- **issue_number**: The number of the issue that was just opened. This is used to post a comment if a similar issue is found.
- **weaviate_url**: The endpoint of your Weaviate instance (e.g., `https://my-weaviate-instance.com`).
- **weaviate_api_key**: Secret key for accessing your Weaviate instance securely.
- **github_token**: Used to authenticate with the GitHub API to post comments on issues. Should have `repo` scope.
- **collection_name**: (Optional) The name of the collection in Weaviate where GitHub issues are stored. Defaults to `GitHubIssues`.
- **github_repository**: (Optional) The full name of the repository in the format `owner/repo`. If omitted, the action uses the repository from the workflow context.

## Outputs

| Name                | Description                                    |
|---------------------|------------------------------------------------|
| `found_similar_issue` | `true` if a similar issue was found, `false` otherwise |
| `comment_posted`      | `true` if a comment was successfully posted, `false` otherwise |
| `error_message`       | Error message if the action failed, empty string otherwise |

## Requirements

- A running Weaviate instance with a collection of GitHub issues.
- The following Python dependencies are used (see `requirements.txt`):
  - `weaviate-client[agents]`
  - `requests`

## Troubleshooting

### Common Issues

1. **"Missing required environment variables"**: Ensure all required secrets are properly configured in your repository settings.

2. **"Failed to connect to Weaviate"**: Verify your Weaviate URL and API key are correct.

3. **"Failed to post comment"**: Check that your GitHub token has the `repo` scope and can post comments on issues.

4. **"Repository full name is not set"**: Make sure to provide the `github_repository` input or ensure the workflow runs in the correct repository context.

### Debugging

The action provides detailed logging. Check the workflow logs for:
- Connection status to Weaviate
- Query execution results
- Comment posting status
- Any error messages


