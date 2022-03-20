from typing import Optional
import datetime
import github

DEFAULT_GITHUB_CLIENT = github.Github()

def hit_limit(
        github_client: github.Github = DEFAULT_GITHUB_CLIENT,
) -> bool:
    remaining, _ = github_client.rate_limiting
    return remaining == 0

def get_next_waittime(
        github_client: github.Github = DEFAULT_GITHUB_CLIENT,
) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(github_client.rate_limiting_resettime)

def wait_for_limit(
        github_client: github.Github = DEFAULT_GITHUB_CLIENT,
) -> None:
    if hit_limit(github_client):
        wait_time = (get_next_waittime(github_client) - datetime.datetime.now()).total_seconds()
        print(f"Hit ratelimit. Waiting {wait_time:.1f}")
        time.sleep(wait_time)

if __name__ == "__main__":
    if hit_limit():
        print(get_next_waittime().isoformat())
