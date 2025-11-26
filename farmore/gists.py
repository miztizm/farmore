"""
Gists backup module for Farmore.

"Gists are just repos that didn't make the cut. But they still deserve a backup." — schema.cx
"""

from dataclasses import dataclass, field
from pathlib import Path
import subprocess

import requests

from .rich_utils import console


@dataclass
class Gist:
    """
    Represents a GitHub Gist.

    "Every gist is a story waiting to be told. Or code waiting to be forgotten." — schema.cx
    """

    id: str
    description: str | None
    public: bool
    html_url: str
    git_pull_url: str
    git_push_url: str
    created_at: str
    updated_at: str
    owner: str | None  # Can be None for anonymous gists
    files: list[dict] = field(default_factory=list)
    comments: int = 0
    truncated: bool = False

    @property
    def name(self) -> str:
        """Get a display name for the gist."""
        if self.description:
            # Sanitize description for use as directory name
            safe_desc = "".join(c if c.isalnum() or c in " -_" else "" for c in self.description)
            safe_desc = safe_desc.strip()[:50]
            if safe_desc:
                return f"{self.id}_{safe_desc.replace(' ', '-')}"
        return self.id


@dataclass
class GistFile:
    """
    Represents a file within a Gist.
    """

    filename: str
    type: str  # MIME type
    language: str | None
    raw_url: str
    size: int
    content: str | None = None  # Content if not truncated


class GistsClient:
    """
    Client for GitHub Gists API.

    "Gists are the junk drawer of GitHub. But organized junk." — schema.cx
    """

    PER_PAGE = 100

    def __init__(self, token: str | None = None, github_host: str | None = None) -> None:
        """Initialize the Gists API client."""
        self.session = requests.Session()

        # Support GitHub Enterprise
        if github_host:
            self.base_url = f"https://{github_host}/api/v3"
        else:
            self.base_url = "https://api.github.com"

        # Set up headers
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Farmore/0.6.0 (https://github.com/miztizm/farmore)",
        }

        if token:
            headers["Authorization"] = f"token {token}"

        self.session.headers.update(headers)

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            self.session.close()

    def __enter__(self) -> "GistsClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _get_next_page_url(self, response: requests.Response) -> str | None:
        """Extract next page URL from Link header."""
        import re

        link_header = response.headers.get("Link")
        if not link_header:
            return None

        links = {}
        for link in link_header.split(","):
            match = re.match(r'<([^>]+)>;\s*rel="([^"]+)"', link.strip())
            if match:
                url, rel = match.groups()
                links[rel] = url

        return links.get("next")

    def get_user_gists(self, username: str | None = None) -> list[Gist]:
        """
        Fetch all gists for a user.

        If username is None, fetches the authenticated user's gists.

        Args:
            username: GitHub username or None for authenticated user

        Returns:
            List of Gist objects
        """
        if username:
            endpoint = f"/users/{username}/gists"
            console.print(f"\n[cyan]📝 Fetching gists for user: {username}[/cyan]")
        else:
            endpoint = "/gists"
            console.print(f"\n[cyan]📝 Fetching YOUR gists (authenticated user)[/cyan]")

        all_gists = []
        url: str | None = f"{self.base_url}{endpoint}"
        params = {"per_page": self.PER_PAGE}

        while url:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data:
                gist = self._parse_gist(item)
                all_gists.append(gist)

            url = self._get_next_page_url(response)
            params = {}  # Only use params on first request

        console.print(f"   [green]✓ Found {len(all_gists)} gists[/green]")
        return all_gists

    def get_starred_gists(self) -> list[Gist]:
        """
        Fetch all starred gists for the authenticated user.

        Returns:
            List of Gist objects
        """
        endpoint = "/gists/starred"
        console.print(f"\n[cyan]⭐ Fetching starred gists[/cyan]")

        all_gists = []
        url: str | None = f"{self.base_url}{endpoint}"
        params = {"per_page": self.PER_PAGE}

        while url:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data:
                gist = self._parse_gist(item)
                all_gists.append(gist)

            url = self._get_next_page_url(response)
            params = {}

        console.print(f"   [green]✓ Found {len(all_gists)} starred gists[/green]")
        return all_gists

    def get_public_gists(self, limit: int = 100) -> list[Gist]:
        """
        Fetch public gists (globally).

        Args:
            limit: Maximum number of gists to return

        Returns:
            List of Gist objects
        """
        endpoint = "/gists/public"
        console.print(f"\n[cyan]🌐 Fetching public gists (limit: {limit})[/cyan]")

        all_gists = []
        url: str | None = f"{self.base_url}{endpoint}"
        params = {"per_page": min(limit, self.PER_PAGE)}

        while url and len(all_gists) < limit:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            for item in data:
                if len(all_gists) >= limit:
                    break
                gist = self._parse_gist(item)
                all_gists.append(gist)

            url = self._get_next_page_url(response)
            params = {}

        console.print(f"   [green]✓ Found {len(all_gists)} public gists[/green]")
        return all_gists

    def get_gist(self, gist_id: str) -> Gist:
        """
        Fetch a single gist by ID.

        Args:
            gist_id: The gist ID

        Returns:
            Gist object with full details
        """
        endpoint = f"/gists/{gist_id}"
        response = self.session.get(f"{self.base_url}{endpoint}", timeout=30)
        response.raise_for_status()
        return self._parse_gist(response.json())

    def _parse_gist(self, data: dict) -> Gist:
        """Parse gist data from API response."""
        files = []
        for filename, file_data in data.get("files", {}).items():
            files.append({
                "filename": filename,
                "type": file_data.get("type", "text/plain"),
                "language": file_data.get("language"),
                "raw_url": file_data.get("raw_url"),
                "size": file_data.get("size", 0),
            })

        owner = None
        if data.get("owner"):
            owner = data["owner"].get("login")

        return Gist(
            id=data["id"],
            description=data.get("description"),
            public=data.get("public", True),
            html_url=data["html_url"],
            git_pull_url=data["git_pull_url"],
            git_push_url=data["git_push_url"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            owner=owner,
            files=files,
            comments=data.get("comments", 0),
            truncated=data.get("truncated", False),
        )


class GistsBackup:
    """
    Handles cloning and updating gists as git repositories.

    "Gists are just repos in disguise. Treat them accordingly." — schema.cx
    """

    def __init__(
        self,
        token: str | None = None,
        github_host: str | None = None,
        dest: Path | None = None,
    ) -> None:
        """
        Initialize the GistsBackup handler.

        Args:
            token: GitHub personal access token
            github_host: GitHub Enterprise hostname (optional)
            dest: Base destination directory for gist backups
        """
        self.client = GistsClient(token=token, github_host=github_host)
        self.dest = dest or Path("backups/gists")
        self.token = token

    def close(self) -> None:
        """Close resources."""
        self.client.close()

    def __enter__(self) -> "GistsBackup":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def backup_user_gists(
        self,
        username: str | None = None,
        include_starred: bool = False,
        skip_existing: bool = False,
    ) -> dict:
        """
        Backup all gists for a user.

        Args:
            username: GitHub username or None for authenticated user
            include_starred: Also backup starred gists
            skip_existing: Skip gists that already exist locally

        Returns:
            Summary dict with counts
        """
        summary = {
            "total": 0,
            "cloned": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        # Get user's own gists
        gists = self.client.get_user_gists(username)

        # Optionally get starred gists
        if include_starred:
            starred = self.client.get_starred_gists()
            # Avoid duplicates
            gist_ids = {g.id for g in gists}
            for sg in starred:
                if sg.id not in gist_ids:
                    gists.append(sg)

        summary["total"] = len(gists)

        # Create destination directory structure
        user_dest = self.dest / (username or "me")
        gists_dest = user_dest / "gists"
        gists_dest.mkdir(parents=True, exist_ok=True)

        # Clone/update each gist
        for gist in gists:
            result = self._backup_single_gist(gist, gists_dest, skip_existing)

            if result["success"]:
                if result["action"] == "cloned":
                    summary["cloned"] += 1
                elif result["action"] == "updated":
                    summary["updated"] += 1
                elif result["action"] == "skipped":
                    summary["skipped"] += 1
            else:
                summary["failed"] += 1
                summary["errors"].append(f"{gist.id}: {result['error']}")

        return summary

    def _backup_single_gist(
        self,
        gist: Gist,
        dest_dir: Path,
        skip_existing: bool = False,
    ) -> dict:
        """
        Backup a single gist.

        Args:
            gist: Gist object to backup
            dest_dir: Destination directory
            skip_existing: Skip if already exists

        Returns:
            Result dict with success, action, error
        """
        gist_path = dest_dir / gist.name

        try:
            if gist_path.exists():
                if skip_existing:
                    console.print(f"   [dim]⏭️  Skipped: {gist.id} (exists)[/dim]")
                    return {"success": True, "action": "skipped", "error": None}

                # Update existing gist
                return self._update_gist(gist, gist_path)
            else:
                # Clone new gist
                return self._clone_gist(gist, gist_path)

        except Exception as e:
            console.print(f"   [red]❌ Failed: {gist.id} - {e}[/red]")
            return {"success": False, "action": "failed", "error": str(e)}

    def _clone_gist(self, gist: Gist, dest_path: Path) -> dict:
        """Clone a gist as a git repository."""
        try:
            # Use git_pull_url for cloning
            clone_url = gist.git_pull_url

            # If we have a token and it's HTTPS, inject credentials
            if self.token and "https://" in clone_url:
                clone_url = clone_url.replace(
                    "https://",
                    f"https://{self.token}:x-oauth-basic@"
                )

            result = subprocess.run(
                ["git", "clone", clone_url, str(dest_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )

            console.print(f"   [green]✓ Cloned: {gist.id}[/green]")
            return {"success": True, "action": "cloned", "error": None}

        except subprocess.CalledProcessError as e:
            return {"success": False, "action": "failed", "error": e.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "action": "failed", "error": "Clone timeout"}

    def _update_gist(self, gist: Gist, gist_path: Path) -> dict:
        """Update an existing gist repository."""
        try:
            # Fetch and pull updates
            result = subprocess.run(
                ["git", "-C", str(gist_path), "pull", "--ff-only"],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            if "Already up to date" in result.stdout:
                console.print(f"   [dim]✓ Up to date: {gist.id}[/dim]")
            else:
                console.print(f"   [green]✓ Updated: {gist.id}[/green]")

            return {"success": True, "action": "updated", "error": None}

        except subprocess.CalledProcessError as e:
            return {"success": False, "action": "failed", "error": e.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "action": "failed", "error": "Update timeout"}
