#!/usr/bin/env python3
import os
import re
import time
import requests
from datetime import datetime, timedelta, timezone

USERNAME = 'gsarmaonline'
TOKEN = os.environ['GITHUB_TOKEN']
HEADERS = {'Authorization': f'token {TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
GQL_HEADERS = {'Authorization': f'bearer {TOKEN}', 'Content-Type': 'application/json'}


def gql(query):
    r = requests.post('https://api.github.com/graphql', json={'query': query}, headers=GQL_HEADERS)
    r.raise_for_status()
    return r.json()


def get_contributions_by_repo():
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    query = f'''
    {{
      user(login: "{USERNAME}") {{
        contributionsCollection(from: "{one_year_ago}", to: "{now}") {{
          commitContributionsByRepository(maxRepositories: 25) {{
            repository {{
              name
              nameWithOwner
              url
            }}
            contributions {{
              totalCount
            }}
          }}
        }}
      }}
    }}
    '''
    data = gql(query)
    return data['data']['user']['contributionsCollection']['commitContributionsByRepository']


def get_commit_stats(repo_name, since):
    url = f'https://api.github.com/repos/{repo_name}/commits'
    params = {'author': USERNAME, 'since': since, 'per_page': 50}
    r = requests.get(url, headers=HEADERS, params=params)
    if r.status_code != 200:
        return 0, 0
    commits = r.json()
    if not isinstance(commits, list):
        return 0, 0

    additions = deletions = 0
    for commit in commits[:30]:
        r2 = requests.get(f'https://api.github.com/repos/{repo_name}/commits/{commit["sha"]}', headers=HEADERS)
        if r2.status_code == 200:
            stats = r2.json().get('stats', {})
            additions += stats.get('additions', 0)
            deletions += stats.get('deletions', 0)
        time.sleep(0.1)
    return additions, deletions


def update_readme(repos):
    with open('README.md') as f:
        content = f.read()

    lines = ['<!-- TOP_REPOS_START -->',
             '### 🚀 Most Active Repos (Last Year)', '']
    for repo in repos:
        add_str = f'+{repo["additions"]:,}'
        del_str = f'-{repo["deletions"]:,}'
        lines.append(f'- [{repo["name"]}]({repo["url"]}) — {repo["commits"]:,} commits, {add_str} / {del_str}')
    lines += ['', '<!-- TOP_REPOS_END -->']
    new_section = '\n'.join(lines)

    if '<!-- TOP_REPOS_START -->' in content:
        content = re.sub(
            r'<!-- TOP_REPOS_START -->.*?<!-- TOP_REPOS_END -->',
            new_section, content, flags=re.DOTALL
        )
    else:
        content = content.replace('---\n\n### 🔗 Connect', f'{new_section}\n\n---\n\n### 🔗 Connect')

    with open('README.md', 'w') as f:
        f.write(content)


def main():
    one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    print('Fetching contribution data...')
    repo_contributions = get_contributions_by_repo()

    results = []
    for entry in repo_contributions:
        repo_name = entry['repository']['nameWithOwner']
        print(f'  {repo_name} ({entry["contributions"]["totalCount"]} commits)...')
        additions, deletions = get_commit_stats(repo_name, one_year_ago)
        results.append({
            'name': entry['repository']['name'],
            'url': entry['repository']['url'],
            'commits': entry['contributions']['totalCount'],
            'additions': additions,
            'deletions': deletions,
        })

    results.sort(key=lambda x: x['commits'], reverse=True)
    top10 = results[:10]

    print('\nTop 10:')
    for r in top10:
        print(f'  {r["name"]}: {r["commits"]} commits, +{r["additions"]:,}/-{r["deletions"]:,}')

    update_readme(top10)
    print('\nREADME updated!')


if __name__ == '__main__':
    main()
