from typing import List, Tuple, Mapping, Any, cast, Optional
import logging
from pathlib import Path
import datetime
import time
import urllib.parse
import re
import os
import warnings

import github
import requests
from charmonium.cache import memoize, MemoizedGroup
#from rich.progress import track as tqdm
from tqdm import tqdm
from ascl_net_scraper import scrape_index, DetailedCodeRecord

from .ratelimit_check import wait_for_limit

group = MemoizedGroup(size="10MiB")

github_regex = re.compile(r"https?://github.com/(?P<author>[a-zA-Z0-9\.\-]*)/(?P<repo>[a-zA-Z0-9\.\-]*)")

def parse_github_url(github_url: str) -> Tuple[str, Optional[str]]:
    github_url_parsed = urllib.parse.urlparse(github_url)
    if github_url_parsed.netloc != "github.com":
        raise ValueError(f"{github_url} is not a github.com url.")
    path = Path(github_url_parsed.path).parts
    user = path[1]
    if len(path) > 2:
        repo = path[2]
        if repo.endswith(".git"):
            repo = repo[:-4]
    else:
        repo = None
    return user, repo

github_client = github.Github(os.environ.get("GITHUB_TOKEN"))

@memoize(group=group)
def get_repos(record: DetailedCodeRecord) -> List[Tuple[int, DetailedCodeRecord, str]]:
    results = []
    if record.github is not None:
        try:
            user, repo = parse_github_url(record.github)
        except ValueError:
            user, repo = None, None
        if user and repo:
            wait_for_limit(github_client)
            try:
                repo_objs = [github_client.get_repo(f"{user}/{repo}")]
            except github.GithubException as e:
                print(f"{type(e).__name__}: {record.url} {record.github}")
                repo_objs = []
        if user and not repo:
            repo_objs = []
            print(f"Unknown repo for {record.github}")
        #     wait_for_limit()
        #     repo_objs = list(github_client.get_user(user).get_repos())
        #     print(f"{record.url} returned {len(repo_objs)} repos")
        else:
            repo_objs = []
        for repo_obj in repo_objs:
            results.append((repo_obj.stargazers_count, record, repo_obj.html_url))
    return results

def get_results(n: Optional[int] = None) -> List[Tuple[int, DetailedCodeRecord, str]]:
    results: List[Tuple[int, DetailedCodeRecord, str]] = []
    index_list = scrape_index(n)
    for index_record in tqdm(index_list):
        record = index_record.get_details()
        results.extend(get_repos(record))
    return sorted(results, key=lambda obj: obj[0])

# __name__ == "__main__" is needed so pytest ignores this.
if __name__ == "__main__":
    logger = logging.getLogger("charmonium.freeze")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler("freeze.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    logger.debug("Program %d", os.getpid())

    logger = logging.getLogger("charmonium.cache.ops")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler("cache.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    logger.debug("Program %d", os.getpid())

    import warnings
    warnings.filterwarnings("ignore", category=UserWarning)

    results = get_results(None)
    results = sorted(results, reverse=True, key=lambda triplet: triplet[0])
    for count, record, url in results[:40]:
        print(count, record.url, url)
