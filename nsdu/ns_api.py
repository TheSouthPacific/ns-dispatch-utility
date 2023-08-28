"""Wrappers for NationStates API calls.
"""

import re

import nationstates

from nsdu import exceptions


class OwnerNationNotSet(exceptions.DispatchApiError):
    pass


def convert_to_html_entities(text: str) -> bytes:
    """Convert special characters to HTML entities

    Args:
        text (str): Text

    Returns:
        str: Converted text
    """

    return text.encode("ascii", "xmlcharrefreplace")


def raise_nsdu_exception(err: Exception) -> None:
    """Reraise NSDU-specific exceptions from API wrapper's exceptions."""

    if "Unknown dispatch" in str(err):
        raise exceptions.UnknownDispatchError from err
    if "not the author of this dispatch" in str(err):
        raise exceptions.NotOwnerDispatchError from err
    if err == nationstates.exceptions.Forbidden:
        raise exceptions.NationLoginError from err

    raise exceptions.DispatchApiError from err


class AuthApi:
    """Wrapper for authentication-related NationStates API calls."""

    def __init__(self, user_agent: str) -> None:
        """Wrapper for login-related NationStates API calls.

        Args:
            user_agent (str): API call's user agent
        """
        self.original_api = nationstates.Nationstates(
            user_agent=user_agent, enable_beta=True
        )

    def get_autologin_code(self, nation_name: str, password: str) -> str:
        """Get autologin code of a nation from its password.

        Args:
            nation_name (str): Nation's name
            password (str): Nation's password

        Raises:
            exceptions.NationLoginError: Failed to log in to the nation

        Returns:
            str: Autologin code
        """

        nation = self.original_api.nation(nation_name, password=password)

        try:
            resp = nation.get_shards("ping", full_response=True)
            return resp["headers"]["X-Autologin"]  # type: ignore
        except nationstates.exceptions.Forbidden as err:
            raise exceptions.NationLoginError from err

    def verify_autologin_code(self, nation_name: str, autologin_code: str) -> bool:
        """Verify if an autologin code can log in to the provided nation.

        Args:
            nation_name (str): Nation's name
            autologin_code (str): Nation's autologin code

        Raises:
            exceptions.NationLoginError: Failed to log in to the nation
        """

        nation = self.original_api.nation(nation_name, autologin=autologin_code)

        try:
            nation.get_shards("ping")
            return True
        except nationstates.exceptions.Forbidden:
            return False


class DispatchApi:
    """Wrapper for dispatch-related NationStates API calls."""

    def __init__(self, user_agent: str) -> None:
        """Wrapper for dispatch-related NationStates API calls.

        Args:
            user_agent (str): API call's user agent
        """
        self.original_api = nationstates.Nationstates(
            user_agent=user_agent, enable_beta=True
        )
        self.owner_nation = None

    def set_owner_nation(self, nation_name: str, autologin: str) -> None:
        """Set the nation to perform dispatch API calls on.

        Args:
            nation_name (str): Nation's name
            autologin (str): Nation's autologin code
        """

        self.owner_nation = self.original_api.nation(nation_name, autologin=autologin)

    def create_dispatch(
        self, title: str, text: str, category: str, subcategory: str
    ) -> str:
        """Create a dispatch.

        Args:
            title (str): Dispatch title
            text (str): Dispatch text
            category (str): Dispatch category number
            subcategory (str): Dispatch subcategory number
        Returns:
            str: New dispatch ID
        """

        if self.owner_nation is None:
            raise OwnerNationNotSet

        try:
            resp = self.owner_nation.create_dispatch(
                title=title,
                text=convert_to_html_entities(text),
                category=category,
                subcategory=subcategory,
            )
        except nationstates.exceptions.APIError as err:
            raise_nsdu_exception(err)

        matches = re.search("id=(\\d+)", resp["success"])  # type: ignore
        if matches is None:
            raise exceptions.DispatchApiError(
                "No dispatch ID found in dispatch API response"
            )
        new_dispatch_id = matches.group(1)
        if not isinstance(new_dispatch_id, str):
            raise exceptions.DispatchApiError(
                "No dispatch ID found in dispatch API response"
            )
        return new_dispatch_id

    def edit_dispatch(
        self, dispatch_id: str, title: str, text: str, category: str, subcategory: str
    ) -> None:
        """Edit a dispatch.

        Args:
            dispatch_id (str): Dispatch ID
            title (str): Dispatch title
            text (str): Dispatch text
            category (str): Dispatch category number
            subcategory (str): Dispatch subcategory number
        """

        if self.owner_nation is None:
            raise OwnerNationNotSet

        try:
            self.owner_nation.edit_dispatch(
                dispatch_id=dispatch_id,
                title=title,
                text=convert_to_html_entities(text),
                category=category,
                subcategory=subcategory,
            )
        except nationstates.exceptions.APIError as err:
            raise_nsdu_exception(err)

    def remove_dispatch(self, dispatch_id: str) -> None:
        """Delete a dispatch.

        Args:
            dispatch_id (str): Dispatch ID
        """

        if self.owner_nation is None:
            raise OwnerNationNotSet

        try:
            self.owner_nation.remove_dispatch(dispatch_id=dispatch_id)
        except nationstates.exceptions.APIError as err:
            raise_nsdu_exception(err)
