#!/bin/bash

# Script to merge all open pull requests into main
# Usage: ./merge_prs.sh [--dry-run] [--token YOUR_GITHUB_TOKEN]
#
# Requirements:
#   - GitHub CLI (gh) installed: https://cli.github.com/
#   - Authenticated with GitHub: `gh auth login`
#   OR
#   - GitHub token passed via --token flag or GITHUB_TOKEN env var

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_OWNER="Finnlayy"
REPO_NAME="Neo_Fabel"
TARGET_BRANCH="main"
DRY_RUN=false
GITHUB_TOKEN=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --token)
      GITHUB_TOKEN="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

echo -e "${BLUE}=== Neo Fabel PR Merge Script ===${NC}"
echo -e "Repository: ${REPO_OWNER}/${REPO_NAME}"
echo -e "Target Branch: ${TARGET_BRANCH}"
echo -e "Dry Run: ${DRY_RUN}"
echo ""

# Check for GitHub CLI
if ! command -v gh &> /dev/null; then
  echo -e "${RED}Error: GitHub CLI (gh) is not installed.${NC}"
  echo "Install it from: https://cli.github.com/"
  exit 1
fi

# Set token if provided
if [ -n "$GITHUB_TOKEN" ]; then
  export GH_TOKEN="$GITHUB_TOKEN"
fi

# Verify authentication
if ! gh auth status &> /dev/null; then
  echo -e "${RED}Error: Not authenticated with GitHub${NC}"
  echo "Please run: gh auth login"
  exit 1
fi

echo -e "${BLUE}Fetching open pull requests...${NC}"
echo ""

# Get all open PRs
prs=$(gh pr list --repo "${REPO_OWNER}/${REPO_NAME}" --state open --json number,title,mergeable --jq '.[].number' 2>/dev/null)

if [ -z "$prs" ]; then
  echo -e "${YELLOW}No open pull requests found.${NC}"
  exit 0
fi

# Count PRs
pr_count=$(echo "$prs" | wc -l)
echo -e "${GREEN}Found ${pr_count} open pull request(s)${NC}"
echo ""

# Track statistics
merged=0
failed=0
skipped=0
conflicts=0

# Merge each PR
for pr_number in $prs; do
  echo -e "${BLUE}---${NC}"
  
  # Get PR details
  pr_info=$(gh pr view "$pr_number" --repo "${REPO_OWNER}/${REPO_NAME}" --json title,mergeable,state --jq '{title: .title, mergeable: .mergeable, state: .state}' 2>/dev/null)
  
  pr_title=$(echo "$pr_info" | jq -r '.title')
  pr_mergeable=$(echo "$pr_info" | jq -r '.mergeable')
  
  echo -e "PR #${pr_number}: ${pr_title}"
  echo -e "Mergeable: ${pr_mergeable}"
  
  # Check if mergeable
  if [ "$pr_mergeable" = "false" ]; then
    echo -e "${YELLOW}⚠️  Skipping: Has conflicts or unmet requirements${NC}"
    conflicts=$((conflicts + 1))
    continue
  fi
  
  # Perform merge
  if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}[DRY RUN] Would merge PR #${pr_number}${NC}"
    merged=$((merged + 1))
  else
    echo -e "${BLUE}Merging PR #${pr_number}...${NC}"
    
    if gh pr merge "$pr_number" \
      --repo "${REPO_OWNER}/${REPO_NAME}" \
      --merge \
      --delete-branch 2>/dev/null; then
      echo -e "${GREEN}✓ Successfully merged PR #${pr_number}${NC}"
      merged=$((merged + 1))
    else
      echo -e "${RED}✗ Failed to merge PR #${pr_number}${NC}"
      failed=$((failed + 1))
    fi
  fi
done

echo ""
echo -e "${BLUE}=== Merge Summary ===${NC}"
echo -e "Merged: ${GREEN}${merged}${NC}"
echo -e "Failed: ${RED}${failed}${NC}"
echo -e "Skipped (conflicts): ${YELLOW}${conflicts}${NC}"
echo ""

if [ "$failed" -gt 0 ]; then
  echo -e "${YELLOW}Note: Some PRs failed to merge. Check GitHub for details.${NC}"
  exit 1
fi

if [ "$conflicts" -gt 0 ]; then
  echo -e "${YELLOW}Note: ${conflicts} PR(s) have conflicts and need to be rebased first.${NC}"
fi

if [ "$DRY_RUN" = true ]; then
  echo -e "${YELLOW}This was a dry run. No changes were made.${NC}"
  echo -e "To actually merge, run: ${BLUE}./merge_prs.sh${NC}"
else
  echo -e "${GREEN}All mergeable PRs have been processed!${NC}"
fi

exit 0
