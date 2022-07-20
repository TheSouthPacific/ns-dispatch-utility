"""Adapter for the pynationstates NS API wrapper
"""

import re

import nationstates

from nsdu import exceptions


def convert_to_html_entities(text):
    """Convert special characters to HTML entities

    Args:
        text (str): Text

    Returns:
        str: Converted text
    """

    return text.encode("ascii", "xmlcharrefreplace")


def reraise_exception(err):
    """Reraise appropriate exceptions."""

    if "Unknown dispatch" in str(err):
        raise exceptions.UnknownDispatchError from err
    if "not the author of this dispatch" in str(err):
        raise exceptions.NotOwnerDispatchError from err

    raise exceptions.DispatchApiError from err


class DispatchApi:
    """Wrapper around pynationstates for dispatch functions.

    Args:
        user_agent (str): User agent
    """

    def __init__(self, user_agent):
        self.api = nationstates.Nationstates(user_agent=user_agent, enable_beta=True)
        self.owner_nation = None

    def login(self, nation_name, password=None, autologin=None):
        """Get nation and test login.

        Args:
            nation_name (str): Nation name
            password (str): Nation password

        Returns:
            str or None: X-Autologin or None if doesn't login via password
        """

        if autologin is None:
            self.owner_nation = self.api.nation(nation_name, password=password)
        else:
            self.owner_nation = self.api.nation(nation_name, autologin=autologin)

        try:
            resp_headers = self.owner_nation.get_shards("ping", full_response=True)[
                "headers"
            ]
        except nationstates.exceptions.Forbidden as err:
            raise exceptions.NationLoginError from err

        if password is not None:
            if "X-Autologin" not in resp_headers:
                raise exceptions.NationLoginError

            return resp_headers["X-Autologin"]

        return None

    def create_dispatch(self, title, text, category, subcategory):
        """Create a dispatch.

        Args:
            title (str): Dispatch title
            text (str): Dispatch text
            category (str): Dispatch category number
            subcategory (str): Dispatch subcategory number
        Returns:
            str: New dispatch ID
        """

        resp = self.owner_nation.create_dispatch(
            title=title,
            text=convert_to_html_entities(text),
            category=category,
            subcategory=subcategory,
        )

        new_dispatch_id = re.search("id=(\\d+)", resp["success"]).group(1)
        return new_dispatch_id

    def edit_dispatch(self, dispatch_id, title, text, category, subcategory):
        """Edit a dispatch.

        Args:
            dispatch_id (str): Dispatch ID
            title (str): Dispatch title
            text (str): Dispatch text
            category (str): Dispatch category number
            subcategory (str): Dispatch subcategory number
        """

        try:
            self.owner_nation.edit_dispatch(
                dispatch_id=dispatch_id,
                title=title,
                text=convert_to_html_entities(text),
                category=category,
                subcategory=subcategory,
            )
        except nationstates.exceptions.APIUsageError as err:
            reraise_exception(err)

    def remove_dispatch(self, dispatch_id):
        """Delete a dispatch.

        Args:
            dispatch_id (str): Dispatch ID
        """

        try:
            self.owner_nation.remove_dispatch(dispatch_id=dispatch_id)
        except nationstates.exceptions.APIUsageError as err:
            reraise_exception(err)
