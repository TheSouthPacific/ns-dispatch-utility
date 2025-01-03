"""Wrappers for NationStates API calls.
"""

import re

import nationstates
from nationstates import exceptions as ns_exceptions
from nationstates.objects import Nation

from nsdu import exceptions


class NsApiError(exceptions.AppError):
    """NationStates API error."""


class DispatchApiError(NsApiError):
    """Dispatch API error."""


class AuthApiError(NsApiError):
    """Auth API error."""


class OwnerNationNotSet(AuthApiError):
    """Owner nation is not set."""


class AuthApi:
    """Wrapper for authentication-related NationStates API calls."""

    def __init__(self, user_agent: str) -> None:
        """Wrapper for authentication-related NationStates API calls.

        Args:
            user_agent (str): User agent for API calls
        """

        self.original_api = nationstates.Nationstates(
            user_agent=user_agent, enable_beta=True
        )

    def get_autologin_code(self, nation_name: str, password: str) -> str:
        """Get autologin code of a nation from its password.

        Args:
            nation_name (str): Nation name
            password (str): Password

        Raises:
            exceptions.NationLoginError: Failed to login

        Returns:
            str: Autologin code
        """

        nation = self.original_api.nation(nation_name, password=password)

        try:
            resp = nation.get_shards("ping", full_response=True)
            return resp["headers"]["X-Autologin"]  # type: ignore
        except ns_exceptions.Forbidden as err:
            raise AuthApiError(f'Failed to log in to nation "{nation_name}"') from err
        except ns_exceptions.NotFound as err:
            raise AuthApiError(f'Nation "{nation_name}" does not exist') from err

    def verify_autologin_code(self, nation_name: str, autologin_code: str) -> bool:
        """Verify if an autologin code can log in to a nation.

        Args:
            nation_name (str): Nation name
            autologin_code (str): Autologin code

        Raises:
            exceptions.NationLoginError: Failed to login
        """

        nation = self.original_api.nation(nation_name, autologin=autologin_code)

        try:
            nation.get_shards("ping")
            return True
        except ns_exceptions.Forbidden:
            return False


def convert_to_html_entities(text: str) -> bytes:
    """Convert special characters to HTML entities

    Args:
        text (str): Text

    Returns:
        bytes: Converted text as bytes
    """

    return text.encode("ascii", "xmlcharrefreplace")


def parse_resp_for_new_dispatch_id(resp_text: str) -> str:
    """Get the dispatch ID of a new dispatch from API response text.

    Args:
        resp_text (str): API response text

    Raises:
        DispatchApiError: No dispatch ID found in API response

    Returns:
        str: Dispatch ID
    """

    matches = re.search("id=(\\d+)", resp_text)

    if matches is None:
        raise DispatchApiError("No dispatch ID found in API response")

    dispatch_id = matches.group(1)
    if not isinstance(dispatch_id, str):
        raise DispatchApiError("No dispatch ID found in API response")

    return dispatch_id


class DispatchApi:
    """Wrapper for dispatch-related NationStates API calls."""

    def __init__(self, user_agent: str) -> None:
        """Wrapper for dispatch-related NationStates API calls.

        Args:
            user_agent (str): User agent for API calls
        """
        self.original_api = nationstates.Nationstates(
            user_agent=user_agent, enable_beta=True
        )
        self.nation: Nation | None = None

    def set_nation(self, nation_name: str, autologin: str) -> None:
        """Set the nation to perform dispatch API calls on.

        Args:
            nation_name (str): Nation name
            autologin (str): Autologin code
        """

        self.nation = self.original_api.nation(nation_name, autologin=autologin)

    def create_dispatch(
        self, title: str, text: str, category: str, subcategory: str
    ) -> str:
        """Create a dispatch.

        Args:
            title (str): Title
            text (str): Text content
            category (str): Category number
            subcategory (str): Subcategory number

        Returns:
            str: ID of new dispatch
        """

        if self.nation is None:
            raise OwnerNationNotSet

        try:
            resp = self.nation.create_dispatch(
                title=title,
                text=convert_to_html_entities(text),
                category=category,
                subcategory=subcategory,
            )
        except ns_exceptions.APIError as err:
            raise DispatchApiError(err) from err

        return parse_resp_for_new_dispatch_id(resp["success"])  # type: ignore

    def edit_dispatch(
        self, dispatch_id: str, title: str, text: str, category: str, subcategory: str
    ) -> None:
        """Edit a dispatch.

        Args:
            dispatch_id (str): Dispatch ID
            title (str): Title
            text (str): Text content
            category (str): Category number
            subcategory (str): Subcategory number
        """

        if self.nation is None:
            raise OwnerNationNotSet

        try:
            self.nation.edit_dispatch(
                dispatch_id=dispatch_id,
                title=title,
                text=convert_to_html_entities(text),
                category=category,
                subcategory=subcategory,
            )
        except ns_exceptions.APIError as err:
            raise DispatchApiError(err) from err

    def delete_dispatch(self, dispatch_id: str) -> None:
        """Delete a dispatch.

        Args:
            dispatch_id (str): Dispatch ID
        """

        if self.nation is None:
            raise OwnerNationNotSet

        try:
            self.nation.remove_dispatch(dispatch_id=dispatch_id)
        except ns_exceptions.APIError as err:
            raise DispatchApiError(err) from err
