from typing import List, TypedDict
from requests import request, post
from os import getenv

from utils.constants import BASE_URL


class Task(TypedDict):
    userId: str
    name: str
    duration: int
    deadline: str  # MMDD

def get_google_oauth_login_url(telegram_user_id: str, username: str):
    # Make a HTTP GET request to BASE_URL/get_google_oauth_url

    url = f"{BASE_URL}/get_google_oauth_url"
    res = request(
        method="GET",
        url=url,
        headers={
            "Content-Type": "application/json",
        },
        params={
            "telegram_user_id": telegram_user_id,
            "username": username,
        },
    )

    url: str = res.json()["url"]
    return url


def get_user(tele_user_id: str):
    # Make a HTTP request to BASE_URL/users/telegram/{user_id}

    user_res = request(
        method="GET",
        url=f"{BASE_URL}/users/telegram/" + tele_user_id,
        headers={
            "Content-Type": "application/json",
        },
    )

    user = user_res.json()
    return user


def add_tasks(task: Task):
    url_post = f"{BASE_URL}/tasks"
    post(url_post, json=task)
