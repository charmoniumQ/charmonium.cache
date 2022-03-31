if True:
    import logging
    import os

    logger = logging.getLogger("charmonium.cache.ops")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler("cache.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    logger.debug("Program %d", os.getpid())

import datetime
import os
import re
import time
import urllib.parse
import warnings
from pathlib import Path
from typing import Any, Hashable, List, Mapping, Optional, Set, Tuple, cast

import github
import requests
from ascl_net_scraper import DetailedCodeRecord, scrape_index  # type: ignore
from charmonium.cache import MemoizedGroup, memoize

# from rich.progress import track as tqdm
from tqdm import tqdm

from .ratelimit_check import wait_for_limit

group = MemoizedGroup(size="100MiB", fine_grain_persistence=False)

github_regex = re.compile(
    r"https?://github.com/(?P<author>[a-zA-Z0-9\.\-]*)/(?P<repo>[a-zA-Z0-9\.\-]*)"
)


def parse_github_url(github_url: str) -> Tuple[str, Optional[str]]:
    github_url_parsed = urllib.parse.urlparse(github_url)
    if github_url_parsed.netloc != "github.com":
        raise ValueError(f"{github_url} is not a github.com url.")
    path = Path(github_url_parsed.path).parts
    user = path[1]
    repo: Optional[str]
    if len(path) > 2:
        repo = path[2]
        if repo.endswith(".git"):
            repo = repo[:-4]
    else:
        repo = None
    return user, repo


if "GITHUB_TOKEN" in os.environ:
    print("Using $GITHUB_TOKEN")

github_client = github.Github(os.environ.get("GITHUB_TOKEN"))

import charmonium.freeze.lib


@charmonium.freeze.lib.freeze_dispatch.register(type(github_client))
def _(obj: github.Github, tabu: Set[int], level: int) -> Hashable:
    return "github thingy"


@memoize(group=group)
def get_repos(record: DetailedCodeRecord) -> List[Tuple[int, DetailedCodeRecord, str]]:
    mresults = []
    if record.github is not None:
        user: Optional[str]
        repo: Optional[str]
        try:
            user, repo = parse_github_url(record.github)
        except ValueError:
            user, repo = None, None
        if user and repo:
            wait_for_limit(github_client, verbose=True)
            try:
                repo_objs = [github_client.get_repo(f"{user}/{repo}")]
            except github.GithubException as e:
                print(f"{type(e).__name__}: {record.url} {record.github}")
                repo_objs = []
        elif user and not repo:
            repo_objs = []
            print(f"Unknown repo for {record.github}")
        #     wait_for_limit()
        #     repo_objs = list(github_client.get_user(user).get_repos())
        #     print(f"{record.url} returned {len(repo_objs)} repos")
        else:
            repo_objs = []
        for repo_obj in repo_objs:
            mresults.append((repo_obj.stargazers_count, record, repo_obj.html_url))
    return mresults


def get_results(n: Optional[int] = None) -> List[Tuple[int, DetailedCodeRecord, str]]:
    results: List[Tuple[int, DetailedCodeRecord, str]] = []
    index_list = list(scrape_index(n))
    print("here1")
    for index_record in tqdm(index_list, desc="Getting details"):
        record = index_record.get_details()
        repos = get_repos(record)
        print(record.url, len(repos))
        results.extend(repos)
    return sorted(results, key=lambda obj: obj[0], reverse=True)


# __name__ == "__main__" is needed so pytest ignores this.
if __name__ == "__main__":

    import warnings

    from charmonium.cache.memoize import CacheThrashingWarning

    warnings.filterwarnings("ignore", category=CacheThrashingWarning)

    results = get_results(1500)
    for count, record, url in results[:100]:
        print(count, record.url, url)
