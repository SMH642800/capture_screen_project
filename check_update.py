import requests

class CheckUpdate:
    def __init__(self):
        # get github info
        github_repository = "SMH642800/capture_screen_project"
        github_api_url = f"https://api.github.com/repos/{github_repository}/releases/latest"


import requests

class UpdateChecker:
    def __init__(self, github_repository, current_version):
        self.github_repository = github_repository
        self.current_version = current_version
        self.github_api_url = f"https://api.github.com/repos/{github_repository}/releases/latest"

    def check_for_updates(self):
        try:
            response = requests.get(self.github_api_url)
            response.raise_for_status()
            release_info = response.json()

            latest_version = release_info["tag_name"]

            if latest_version != self.current_version:
                message = f"A new version ({latest_version}) is available! You can download it from {release_info['html_url']}"
            else:
                message = "Your app is up to date."

            return message
        except requests.exceptions.RequestException as e:
            return f"Error checking for updates: {str(e)}"
