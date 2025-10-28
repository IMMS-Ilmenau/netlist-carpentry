from __future__ import annotations

from typing import Dict, List, Optional, Union

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from typing_extensions import TypeAlias

BASIC_LEAF = Union[str, int, float, bool, None]
NESTED_DICT = Union[BASIC_LEAF, Dict[str, 'NESTED_DICT'], List['NESTED_DICT']]
METADATA_DICT: TypeAlias = Dict[str, Dict[str, NESTED_DICT]]


class MetadataMixin(METADATA_DICT):
    """
    A mixin class that provides a structured way to manage metadata categorized by keys.

    This class extends a dictionary structure where each key maps to another dictionary
    of metadata entries. It ensures that values added to categories are dictionaries,
    and provides convenient methods for adding, setting, and retrieving metadata.
    """

    def __setitem__(self, key: str, value: NESTED_DICT) -> None:
        """
        Set an item in the metadata dictionary.

        Args:
            key (str): The category name to set.
            value (NESTED_DICT): The value to assign. Must be a dictionary.

        Raises:
            ValueError: If the value is not a dictionary.
        """
        if not isinstance(value, dict):
            raise ValueError(f'Value must be a dictionary for the given category, but got a {type(value).__name__} instead for category {key}!')
        return super().__setitem__(key, value)

    def __getattr__(self, name: str) -> Dict[str, NESTED_DICT]:
        """
        Retrieve a category from the metadata by attribute access.

        In particular, if the metadata object has a category "some_cat", it can be accessed
        directly via `metadata["some_cat"]` but also via `metadata.some_cat`.
        Calling `metadata.nonexisting_category` will raise an AttributeError.

        Args:
            name (str): The name of the category to retrieve.

        Returns:
            Dict[str, NESTED_DICT]: The dictionary of metadata for the specified category.

        Raises:
            AttributeError: If the category does not exist.
        """
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(f'No category called {name}') from e

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        """
        Generate a Pydantic core schema for this class.

        This is required if the class using this mixin extends `pydantic.BaseModel`.

        Args:
            source_type (object): The source type.
            handler (GetCoreSchemaHandler): The handler to use for generating the schema.

        Returns:
            CoreSchema: The generated schema.
        """
        return core_schema.no_info_after_validator_function(cls, handler(str))  # type: ignore[misc]

    @property
    def is_empty(self) -> bool:
        return not any(val for _, val in self.items())

    def has_category(self, category: str) -> bool:
        """
        Check if a category exists in the metadata.

        Args:
            category (str): The name of the category to check.

        Returns:
            bool: True if the category exists, False otherwise.
        """
        return category in self

    def add_category(self, category: str) -> bool:
        """
        Add a new category to the metadata if it does not already exist.

        Args:
            category (str): The name of the category to add.

        Returns:
            bool: True if the category was added, False if it already existed.
        """
        if not self.has_category(category):
            self[category] = {}
            return True
        return False

    def add(self, key: str, value: NESTED_DICT, category: str = 'general') -> bool:
        """
        Add a new key-value pair to a specified category.

        If the category does not exist, it is created.

        Args:
            key (str): The key to add.
            value (NESTED_DICT): The value to assign to the key.
            category (str): The category in which to store the key-value pair.
                Defaults to 'general', which means that if no category is specified,
                the key-value pair will be added to the 'general' category.

        Returns:
            bool: True if the key was added, False if it already existed.
        """
        self.add_category(category)  # Adds a category but only if it does not exist yet
        if key not in self[category]:
            self.set(key, value, category)
            return True
        return False

    def set(self, key: str, value: NESTED_DICT, category: str = 'general') -> None:
        """
        Set a key-value pair in a specified category.

        If the category does not exist, it is created.
        Any previously assigned key-value pairs are overwritten.

        Args:
            key (str): The key to set.
            value (NESTED_DICT): The value to assign to the key.
            category (str): The category in which to store the key-value pair. Defaults to 'general'.
        """
        self.add_category(category)  # Adds a category but only if it does not exist yet
        self[category][key] = value

    def get(self, key: str, default: Optional[NESTED_DICT] = None, category: str = 'general') -> NESTED_DICT:  # type: ignore[override]
        """
        Retrieve a value from a specified category by key.

        `MetaDataMixin.get('key', category='cat')` is equivalent to `MetaDataMixin.cat.get('key')`,
        (given that the category `cat` exists).
        Also, `MetaDataMixin.get('key', 'default', category='cat')` is equivalent to `MetaDataMixin.cat.get('key', 'default')`,
        (given that the category `cat` exists).

        Args:
            key (str): The key to retrieve.
            default (Optional[NESTED_DICT]): The default value if the key is not found. Defaults to None.
            category (str): The category from which to retrieve the key. Defaults to 'general'.

        Returns:
            NESTED_DICT: The value associated with the key, or the default if not found.
        """
        if category in self:
            return self[category].get(key, default)
        return default
