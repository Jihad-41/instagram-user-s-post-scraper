import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from extractors.utils_date import (
    parse_instagram_timestamp,
    format_datetime_readable,
)

logger = logging.getLogger(__name__)

class InstagramScraperError(Exception):
    """Base exception for scraper-related errors."""

@dataclass
class InstagramPost:
    MediaType: Optional[str]
    MediaId: Optional[str]
    postShortCode: Optional[str]
    postURL: Optional[str]
    isVideo: Optional[bool]
    hasAudio: Optional[bool]
    displayURL: Optional[str]
    dimensionWidth: Optional[int]
    dimensionHeight: Optional[int]
    videoViewCount: Optional[int]
    postCaption: Optional[str]
    totalLikes: Optional[int]
    totalComments: Optional[int]
    isAffiliate: Optional[bool]
    isPaidPartnership: Optional[bool]
    commentsDisabled: Optional[bool]
    postDate: Optional[str]
    ownerUsername: Optional[str]
    ownerUserID: Optional[str]
    location: Optional[str]
    viewerCanReshare: Optional[bool]
    productType: Optional[str]
    hashtags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "MediaType": self.MediaType,
            "MediaId": self.MediaId,
            "postShortCode": self.postShortCode,
            "postURL": self.postURL,
            "isVideo": self.isVideo,
            "hasAudio": self.hasAudio,
            "displayURL": self.displayURL,
            "dimensionWidth": self.dimensionWidth,
            "dimensionHeight": self.dimensionHeight,
            "videoViewCount": self.videoViewCount,
            "postCaption": self.postCaption,
            "totalLikes": self.totalLikes,
            "totalComments": self.totalComments,
            "isAffiliate": self.isAffiliate,
            "isPaidPartnership": self.isPaidPartnership,
            "commentsDisabled": self.commentsDisabled,
            "postDate": self.postDate,
            "ownerUsername": self.ownerUsername,
            "ownerUserID": self.ownerUserID,
            "location": self.location,
            "viewerCanReshare": self.viewerCanReshare,
            "productType": self.productType,
            "hashtags": self.hashtags,
        }

class InstagramParser:
    """
    Lightweight Instagram profile scraper using public web endpoints.

    Note: Instagram frequently changes internal APIs. This implementation targets
    the `?__a=1&__d=dis` JSON structure and is intentionally defensive:
    if the expected keys are missing, it raises a descriptive error instead of
    silently failing.
    """

    BASE_URL = "https://www.instagram.com"

    def __init__(self, user_agent: str, timeout: float = 10.0) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self.timeout = timeout

    # -----------------------
    # Public API
    # -----------------------

    def fetch_posts(
        self, username: str, max_posts: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch posts for a public Instagram profile.

        Args:
            username: Instagram handle (without @).
            max_posts: Maximum number of posts to fetch, or None for all visible.

        Returns:
            A list of dictionaries representing posts.
        """
        if not username:
            raise InstagramScraperError("Username must not be empty.")

        posts: List[InstagramPost] = []

        logger.debug("Fetching initial page for '%s'.", username)
        data, page_info = self._fetch_profile_page_json(username=username, max_id=None)
        user = self._extract_user(data)

        posts.extend(self._parse_edges_to_posts(user, username))

        # Handle pagination using `end_cursor` when available.
        while page_info.get("has_next_page"):
            if max_posts is not None and len(posts) >= max_posts:
                logger.info(
                    "Reached max_posts limit (%d) for '%s'.", max_posts, username
                )
                break

            end_cursor = page_info.get("end_cursor")
            if not end_cursor:
                logger.debug("No end_cursor despite has_next_page=True. Stopping.")
                break

            logger.debug(
                "Fetching next page for '%s' with end_cursor=%s", username, end_cursor
            )
            data, page_info = self._fetch_profile_page_json(
                username=username, max_id=end_cursor
            )
            user = self._extract_user(data)
            new_posts = self._parse_edges_to_posts(user, username)
            if not new_posts:
                logger.debug("No new posts returned for '%s'. Stopping pagination.", username)
                break
            posts.extend(new_posts)

        if max_posts is not None and len(posts) > max_posts:
            posts = posts[:max_posts]

        return [p.to_dict() for p in posts]

    # -----------------------
    # HTTP and JSON handling
    # -----------------------

    def _build_profile_url(self, username: str) -> str:
        return f"{self.BASE_URL}/{username}/"

    def _fetch_profile_page_json(
        self, username: str, max_id: Optional[str]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Hit the public JSON endpoint visible for profile pages.

        We first attempt the modern `?__a=1&__d=dis` endpoint. If that fails,
        we fall back to parsing JSON from the HTML <script> tags.
        """
        url = self._build_profile_url(username)
        params: Dict[str, Any] = {"__a": "1", "__d": "dis"}
        if max_id:
            # Historically, `max_id` controls pagination. It may change over time;
            # we still expose it for realistic behavior.
            params["max_id"] = max_id

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise InstagramScraperError(
                f"Network error while fetching profile '{username}': {exc}"
            ) from exc

        if resp.status_code == 404:
            raise InstagramScraperError(
                f"Profile '{username}' not found (HTTP 404). "
                "Make sure the account exists and is public."
            )
        if resp.status_code != 200:
            raise InstagramScraperError(
                f"Unexpected HTTP status {resp.status_code} while fetching '{username}'."
            )

        # Try JSON response first
        try:
            data = resp.json()
            user = self._extract_user(data)
            page_info = self._extract_page_info(user)
            return data, page_info
        except (ValueError, KeyError, InstagramScraperError):
            # Fallback: parse JSON embedded in HTML
            logger.debug(
                "JSON endpoint parsing failed for '%s', falling back to HTML parsing.",
                username,
            )
            html = resp.text
            data_from_html = self._parse_embedded_json(html)
            user = self._extract_user(data_from_html)
            page_info = self._extract_page_info(user)
            return data_from_html, page_info

    def _parse_embedded_json(self, html: str) -> Dict[str, Any]:
        """
        Fallback parser: extract JSON blobs from Instagram HTML.

        We search for `window._sharedData` or any script tag with JSON-like content.
        """
        shared_data_match = re.search(